"""
DA-ToG (Domain-Agnostic Tree-of-Graphs) API endpoints.

Provides endpoints for:
- DA-ToG configuration management
- Taxonomy tree management
- DA-ToG pipeline execution
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from backend.dependencies import get_current_user, require_admin
from backend.services.config_service import config_service
from backend.schemas import TaskConfig


# ─── Request/Response Models ─────────────────────────────


class DAToGConfig:
    """DA-ToG configuration request/response model."""

    taxonomy_path: str
    domain: str = ""
    sampling_strategy: str = "coverage"  # coverage, uniform_branch, depth_weighted
    graph_max_hops: int = 2
    graph_max_nodes: int = 20
    serialization_format: str = "natural_language"  # natural_language, markdown, json
    critic_type: str = "rule"  # llm, rule, none
    critic_min_score: float = 0.6
    generation_target_qa_pairs: int = 100
    batch_size: int = 10


class DAToGPipelineConfig:
    """DA-ToG pipeline execution request."""

    domain_config_path: str
    taxonomy_path: str = ""
    input_file: str = ""
    kg_path: str = ""
    output_path: str = ""
    generate_taxonomy: bool = False
    source_document: str = ""


# ─── Request/Response Models ─────────────────────────────


class SaveDAToGConfigRequest:
    """Save DA-ToG configuration request."""

    domain: str = ""
    taxonomy_path: str = ""
    sampling_strategy: str = "coverage"
    graph_max_hops: int = 2
    graph_max_nodes: int = 20
    serialization_format: str = "natural_language"
    critic_type: str = "rule"
    critic_min_score: float = 0.6
    generation_target_qa_pairs: int = 100
    batch_size: int = 10


class RunDAToGPipelineRequest:
    """Run DA-ToG pipeline request."""

    domain_config_path: str = ""
    taxonomy_path: str = ""
    input_file: str = ""
    kg_path: str = ""
    output_path: str = ""


# ─── DA-ToG Endpoints ─────────────────────────────


@router.post("/datog/config/save", response_model=TaskResponse)
async def save_datog_config(
    request: SaveDAToGConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """保存 DA-ToG 配置"""
    # Check if user is admin (for now, all users can manage)
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    config = config_service.save_config(request.dict())
    if config.get("success"):
        return JSONResponse(content={"message": "配置保存成功"})
    else:
        return JSONResponse(content={"message": "配置保存失败", "error": config.get("error", "detail": config.get("error")})


@router.post("/datog/config/load", response_model=TaskResponse)
async def load_datog_config(
    request: SaveDAToGConfigRequest,
    current_user: User = Depends(get_current_user),
):
    """加载 DA-ToG 配置"""
    # Load user's DA-ToG config (each user can have their own DA-ToG config)
    config = config_service.load_config(current_user.username)

    if config.get("success") and config.get("data"):
        return JSONResponse(content={"message": "配置加载成功", "config": config.get("data")})
    else:
        return JSONResponse(content={"message": "配置加载失败", "error": config.get("error"), "detail": config.get("error")})


@router.get("/datog/taxonomy/save", response_model=TaskResponse)
async def save_taxonomy_tree(
    request: DAToGConfig,
    current_user: User = Depends(get_current_user, require_admin),
    data: DAToGConfigRequest,
):
    """保存 DA-ToG 意图树"""
    # Check admin
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    # Validate taxonomy data
    # For now, just save the tree as JSON
    import json

    # Create taxonomy file path
    user_taxonomies_dir = f"data/taxonomies/{current_user.username}"
    from pathlib import Path
    Path(user_taxonomies_dir).mkdir(parents=True, exist_ok=True)

    taxonomy_filename = f"{data.domain or 'default'}_{timestamp()}.json"
    taxonomy_path = os.path.join(user_taxonomies_dir, taxonomy_filename)

    with open(taxonomy_path, "w", encoding="utf-8") as f:
        json.dump(request.dict(), f, ensure_ascii=False, indent=2)

    return JSONResponse(content={
        "success": True,
        "taxonomy_path": taxonomy_path,
        "domain": data.domain,
        "message": f"意树保存成功"
    })


@router.get("/datog/taxonomy/list", response_model=TaskResponse)
async def list_taxonomy_trees(
    current_user: User = Depends(get_current_user),
):
    """获取用户的所有 DA-ToG 意图树"""
    user_taxonomies_dir = f"data/taxonomies/{current_user.username}"
    from pathlib import Path

    if not os.path.exists(user_taxonomies_dir):
        return JSONResponse(content={
            "success": True,
            "taxonomies": [],
            "message": "暂无意图树"
        })

    taxonomies = []
    for file_path in Path(user_taxonomies_dir).glob("*.json"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                taxonomies.append({
                    "name": file_path.stem,
                    "path": str(file_path),
                    "domain": json.load(f).get("domain", ""),
                    "created_at": None,  # TODO: load from file
                })
        except Exception:
            pass

    return JSONResponse(content={
        "success": True,
        "taxonomies": taxonomies,
        "message": f"找到 {len(taxonomies)} 个意图树"
    })


@router.get("/datog/taxonomy/{taxonomy_id}", response_model=TaskResponse)
async def get_taxonomy_tree(
    taxonomy_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取单个 DA-ToG 意图树详情"""
    from backend.dependencies import get_current_user, require_admin

    # Find the taxonomy file
    user_taxonomies_dir = f"data/taxonomies/{current_user.username}"
    for file_path in Path(user_taxonomies_dir).glob("*.json"):
        if file_path.stem == taxonomy_id:
            taxonomy_path = file_path
            break
    else:
        raise HTTPException(status_code=404, detail=f"未找到意图树 {taxonomy_id}")

    with open(taxonomy_path, "r", encoding="utf-8") as f:
        taxonomy_data = json.load(f)

    return JSONResponse(content={
        "success": True,
        "taxonomy": taxonomy_data,
        "message": "意图树获取成功"
    })


@router.post("/datog/taxonomy/{taxonomy_id}", response_model=TaskResponse)
async def update_taxonomy_tree(
    taxonomy_id: str,
    current_user: User = Depends(get_current_user, require_admin),
    request: DAToGConfig,
):
    """更新 DA-ToG 意图树"""
    # Find and load the taxonomy
    user_taxonomies_dir = f"data/taxonomies/{current_user.username}"
    taxonomy_path = os.path.join(user_taxonomies_dir, f"{taxonomy_id}.json")

    if not os.path.exists(taxonomy_path):
        raise HTTPException(status_code=404, detail=f"意图树不存在: {taxonomy_id}")

    with open(taxonomy_path, "r", encoding="utf-8") as f:
        json.dump(request.dict(), f, ensure_ascii=False, indent=2)

    return JSONResponse(content={
        "success": True,
        "taxonomy": json.load(taxonomy_path),
        "message": f"意图树 {taxonomy_id} 更新成功"
    })


@router.post("/datog/taxonomy/{taxonomy_id}", response_model=TaskResponse)
async def delete_taxonomy_tree(
    taxonomy_id: str,
    current_user: User = Depends(get_current_user, require_admin),
):
    """删除 DA-ToG 意图树"""
    # Find and delete the taxonomy file
    user_taxonomies_dir = f"data/taxonomies/{current_user.username}"
    taxonomy_path = os.path.join(user_taxonomies_dir, f"{taxonomy_id}.json")

    if not os.path.exists(taxonomy_path):
        raise HTTPException(status_code=404, detail=f"意图树不存在: {taxonomy_id}")

    # Also need to check if taxonomy is used by any active task
    # For now, just delete the file
    os.remove(taxonomy_path)

    return JSONResponse(content={"success": True, "message": f"意图树 {taxonomy_id} 删除成功"})


@router.post("/datog/pipeline/run", response_model=TaskResponse)
async def run_datog_pipeline(
    request: RunDAToGPipelineConfig,
    current_user: User = Depends(get_current_user),
):
    """运行 DA-ToG 管道生成数据"""
    # For now, this is a placeholder - the actual implementation
    # should call the graphgen datog CLI via subprocess
    # or integrate DAToGPipeline into the web service

    # For now, return a simulated response
    import asyncio
    import subprocess

    # Get user's config
    config = config_service.load_config(current_user.username)

    # Extract DA-ToG config from user config
    datog_config = config.get("data", {}).get("datog", {})

    if not datog_config:
        return JSONResponse(content={
            "success": True,
            "message": "未配置 DA-ToG 模式，请先配置 DA-ToG"
        })

    # Build command for running datog pipeline
    # This would call: python graphgen_cli.py --datog-config <path> --datog-output <path>
    # For now, return a simulated response
    result = {
        "task_id": f"datog_{asyncio.get_event_loop().time()}",
        "status": "running",
        "output_file": datog_config.get("output_path", ""),
    }

    # Simulate starting the pipeline (async, would be better but this is synchronous endpoint)
    await asyncio.sleep(1)

    # Return the result
    return JSONResponse(content={"success": True, "data": result})


@router.get("/datog/pipeline/status/{task_id}", response_model=TaskResponse)
async def get_pipeline_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取 DA-ToG 管道运行状态"""
    # For now, return placeholder status
    return JSONResponse(content={
        "success": True,
        "task_id": task_id,
        "status": "not_started",
        "message": "DA-ToG 管道功能开发中"
    })
