import re
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

from arborgraph.bases import BaseGraphStorage, BaseKGBuilder, BaseKVStorage, BaseLLMClient, Chunk
from arborgraph.templates import KG_EXTRACTION_PROMPT, KG_SUMMARIZATION_PROMPT
from arborgraph.utils import (
    compute_content_hash,
    detect_main_language,
    handle_single_entity_extraction,
    handle_single_relationship_extraction,
    logger,
    pack_history_conversations,
    split_string_by_multi_markers,
)
from arborgraph.utils.batch_request_manager import BatchRequestManager


class LightRAGKGBuilder(BaseKGBuilder):
    def __init__(
        self, 
        llm_client: BaseLLMClient, 
        max_loop: int = 3,
        cache_storage: Optional[BaseKVStorage] = None,
        enable_cache: bool = True,
        enable_batch_requests: bool = True,
        batch_size: int = 10,
        max_wait_time: float = 0.5
    ):
        super().__init__(llm_client)
        self.max_loop = max_loop
        self.cache_storage = cache_storage
        self.enable_cache = enable_cache and cache_storage is not None
        self.enable_batch_requests = enable_batch_requests
        self.batch_manager: Optional[BatchRequestManager] = None
        if enable_batch_requests:
            self.batch_manager = BatchRequestManager(
                llm_client=llm_client,
                batch_size=batch_size,
                max_wait_time=max_wait_time,
                enable_batching=True
            )

    async def extract(
        self, chunk: Chunk
    ) -> Tuple[Dict[str, List[dict]], Dict[Tuple[str, str], List[dict]]]:
        """
        Extract entities and relationships from a single chunk using the LLM client.
        Supports caching to avoid re-extraction of identical chunks.
        :param chunk
        :return: (nodes_data, edges_data)
        """
        chunk_id = chunk.id
        content = chunk.content
        
        # Check cache first if enabled
        if self.enable_cache:
            chunk_hash = compute_content_hash(content, prefix="extract-")
            cached_result = await self.cache_storage.get_by_id(chunk_hash)
            if cached_result is not None:
                # 用 info 级别记录关键里程碑，保证不同输入时日志结构一致（便于定位差异）
                logger.info("[KG Extract] Cache hit: chunk_id=%s", chunk_id)
                return cached_result["nodes"], cached_result["edges"]

        # step 1: language_detection
        language = detect_main_language(content)

        hint_prompt = KG_EXTRACTION_PROMPT[language]["TEMPLATE"].format(
            **KG_EXTRACTION_PROMPT["FORMAT"], input_text=content
        )
        logger.info(
            "[KG Extract] Start: chunk_id=%s language=%s prompt_len=%d content_len=%d",
            chunk_id,
            language,
            len(hint_prompt),
            len(content),
        )

        # step 2: initial glean
        # 注意：部分 OpenAI-兼容服务在限流/异常边界情况下可能返回空 content（而不是抛异常）。
        # 为了让单 chunk 与合并抽取路径的行为一致，这里将“空响应”视为可重试错误。
        final_result = ""
        max_empty_retries = 3
        for attempt in range(1, max_empty_retries + 1):
            if self.batch_manager:
                final_result = await self.batch_manager.add_request(hint_prompt)
            else:
                final_result = await self.llm_client.generate_answer(hint_prompt)

            if final_result and str(final_result).strip():
                break

            wait_s = min(2 ** attempt, 8)
            logger.warning(
                "[KG Extract] Empty LLM response: chunk_id=%s attempt=%d/%d retry_after=%.1fs prompt_len=%d",
                chunk_id,
                attempt,
                max_empty_retries,
                wait_s,
                len(hint_prompt),
            )
            # 避免引入 asyncio 依赖到文件头：这里局部导入
            import asyncio

            await asyncio.sleep(wait_s)

        if not final_result or not str(final_result).strip():
            raise RuntimeError(
                f"LLM returned empty response for KG extraction (chunk_id={chunk_id}). "
                "This usually indicates upstream throttling, content filtering, or an OpenAI-compatible API returning empty content."
            )

        logger.info(
            "[KG Extract] LLM response received: chunk_id=%s response_len=%d",
            chunk_id,
            len(final_result),
        )
        logger.debug(
            "First extraction result: %s",
            final_result[:200] if len(final_result) > 200 else final_result,
        )

        # step3: iterative refinement
        # history = pack_history_conversations(hint_prompt, final_result)
        # for loop_idx in range(self.max_loop):
        #     if_loop_result = await self.llm_client.generate_answer(
        #         text=KG_EXTRACTION_PROMPT[language]["IF_LOOP"], history=history
        #     )
        #     if_loop_result = if_loop_result.strip().strip('"').strip("'").lower()
        #     if if_loop_result != "yes":
        #         break

        #     glean_result = await self.llm_client.generate_answer(
        #         text=KG_EXTRACTION_PROMPT[language]["CONTINUE"], history=history
        #     )
        #     logger.debug("Loop %s glean: %s", loop_idx + 1, glean_result)

        #     history += pack_history_conversations(
        #         KG_EXTRACTION_PROMPT[language]["CONTINUE"], glean_result
        #     )
        #     final_result += glean_result

        # step 4: 修复并解析结果
        from arborgraph.utils import repair_llm_response
        
        # 使用修复工具预处理响应
        repaired_result = repair_llm_response(
            final_result,
            expected_format="kg_extraction"
        )
        
        logger.info(
            "[KG Extract] Repair complete: chunk_id=%s original_len=%d repaired_len=%d",
            chunk_id,
            len(final_result),
            len(repaired_result),
        )
        
        records = split_string_by_multi_markers(
            repaired_result,
            [
                KG_EXTRACTION_PROMPT["FORMAT"]["record_delimiter"],
                KG_EXTRACTION_PROMPT["FORMAT"]["completion_delimiter"],
            ],
        )

        nodes = defaultdict(list)
        edges = defaultdict(list)

        for record in records:
            match = re.search(r"\((.*)\)", record)
            if not match:
                continue
            inner = match.group(1)

            attributes = split_string_by_multi_markers(
                inner, [KG_EXTRACTION_PROMPT["FORMAT"]["tuple_delimiter"]]
            )

            entity = await handle_single_entity_extraction(attributes, chunk_id)
            if entity is not None:
                nodes[entity["entity_name"]].append(entity)
                continue

            relation = await handle_single_relationship_extraction(attributes, chunk_id)
            if relation is not None:
                key = (relation["src_id"], relation["tgt_id"])
                edges[key].append(relation)

        result = (dict(nodes), dict(edges))
        logger.info(
            "[KG Extract] Parsed: chunk_id=%s records=%d nodes=%d edges=%d",
            chunk_id,
            len(records),
            sum(len(v) for v in result[0].values()),
            sum(len(v) for v in result[1].values()),
        )
        
        # Cache the result if enabled
        if self.enable_cache:
            chunk_hash = compute_content_hash(content, prefix="extract-")
            await self.cache_storage.upsert({
                chunk_hash: {
                    "nodes": result[0],
                    "edges": result[1],
                    "chunk_id": chunk_id
                }
            })
            logger.info("[KG Extract] Cached: chunk_id=%s", chunk_id)
        
        return result

    async def merge_nodes(
        self,
        node_data: tuple[str, List[dict]],
        kg_instance: BaseGraphStorage,
    ) -> None:
        entity_name, node_data = node_data
        entity_types = []
        source_ids = []
        descriptions = []

        node = await kg_instance.get_node(entity_name)
        if node is not None:
            entity_types.append(node["entity_type"])
            source_ids.extend(
                split_string_by_multi_markers(node["source_id"], ["<SEP>"])
            )
            descriptions.append(node["description"])

        # take the most frequent entity_type
        entity_type = sorted(
            Counter([dp["entity_type"] for dp in node_data] + entity_types).items(),
            key=lambda x: x[1],
            reverse=True,
        )[0][0]

        description = "<SEP>".join(
            sorted(set([dp["description"] for dp in node_data] + descriptions))
        )
        description = await self._handle_kg_summary(entity_name, description)

        source_id = "<SEP>".join(
            set([dp["source_id"] for dp in node_data] + source_ids)
        )

        node_data = {
            "entity_type": entity_type,
            "description": description,
            "source_id": source_id,
        }
        await kg_instance.upsert_node(entity_name, node_data=node_data)

    async def merge_edges(
        self,
        edges_data: tuple[Tuple[str, str], List[dict]],
        kg_instance: BaseGraphStorage,
    ) -> None:
        (src_id, tgt_id), edge_data = edges_data

        source_ids = []
        descriptions = []

        edge = await kg_instance.get_edge(src_id, tgt_id)
        if edge is not None:
            source_ids.extend(
                split_string_by_multi_markers(edge["source_id"], ["<SEP>"])
            )
            descriptions.append(edge["description"])

        description = "<SEP>".join(
            sorted(set([dp["description"] for dp in edge_data] + descriptions))
        )
        source_id = "<SEP>".join(
            set([dp["source_id"] for dp in edge_data] + source_ids)
        )

        for insert_id in [src_id, tgt_id]:
            if not await kg_instance.has_node(insert_id):
                await kg_instance.upsert_node(
                    insert_id,
                    node_data={
                        "source_id": source_id,
                        "description": description,
                        "entity_type": "UNKNOWN",
                    },
                )

        description = await self._handle_kg_summary(
            f"({src_id}, {tgt_id})", description
        )

        await kg_instance.upsert_edge(
            src_id,
            tgt_id,
            edge_data={"source_id": source_id, "description": description},
        )

    async def _handle_kg_summary(
        self,
        entity_or_relation_name: str,
        description: str,
        max_summary_tokens: int = 200,
    ) -> str:
        """
        Handle knowledge graph summary

        :param entity_or_relation_name
        :param description
        :param max_summary_tokens
        :return summary
        """

        tokenizer_instance = self.llm_client.tokenizer
        language = detect_main_language(description)

        tokens = tokenizer_instance.encode(description)
        if len(tokens) < max_summary_tokens:
            return description

        use_description = tokenizer_instance.decode(tokens[:max_summary_tokens])
        prompt = KG_SUMMARIZATION_PROMPT[language]["TEMPLATE"].format(
            entity_name=entity_or_relation_name,
            description_list=use_description.split("<SEP>"),
            **KG_SUMMARIZATION_PROMPT["FORMAT"],
        )
        if self.batch_manager:
            new_description = await self.batch_manager.add_request(prompt)
        else:
            new_description = await self.llm_client.generate_answer(prompt)
        logger.info(
            "Entity or relation %s summary: %s",
            entity_or_relation_name,
            new_description,
        )
        return new_description