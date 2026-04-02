import argparse
import os
import time
from importlib.resources import files

import yaml
from dotenv import load_dotenv

from arborgraph.arborgraph import ArborGraph
from arborgraph.utils import logger, set_logger

sys_path = os.path.abspath(os.path.dirname(__file__))

load_dotenv()


def set_working_dir(folder):
    os.makedirs(folder, exist_ok=True)


def save_config(config_path, global_config):
    if not os.path.exists(os.path.dirname(config_path)):
        os.makedirs(os.path.dirname(config_path))
    with open(config_path, "w", encoding="utf-8") as config_file:
        yaml.dump(
            global_config, config_file, default_flow_style=False, allow_unicode=True
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        help="Config parameters for ArborGraph.",
        default=files("arborgraph").joinpath("configs", "aggregated_config.yaml"),
        type=str,
    )
    parser.add_argument(
        "--output_dir",
        help="Output directory for ArborGraph.",
        default=sys_path,
        required=True,
        type=str,
    )

    args = parser.parse_args()

    working_dir = args.output_dir

    with open(args.config_file, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)

    mode = config["generate"]["mode"]
    unique_id = int(time.time())

    output_path = os.path.join(working_dir, "data", "arborgraph", f"{unique_id}")
    set_working_dir(output_path)

    set_logger(
        os.path.join(output_path, f"{unique_id}_{mode}.log"),
        if_stream=True,
    )
    logger.info(
        "ArborGraph with unique ID %s logging to %s",
        unique_id,
        os.path.join(working_dir, f"{unique_id}_{mode}.log"),
    )

    arbor_graph = ArborGraph(unique_id=unique_id, working_dir=working_dir)

    arbor_graph.insert(read_config=config["read"], split_config=config["split"])

    arbor_graph.search(search_config=config["search"])

    if config.get("quiz_and_judge", {}).get("enabled"):
        arbor_graph.quiz_and_judge(quiz_and_judge_config=config["quiz_and_judge"])

    # TODO: add data filtering step here in the future
    # arbor_graph.filter(filter_config=config["filter"])

    arbor_graph.generate(
        partition_config=config["partition"],
        generate_config=config["generate"],
    )

    save_config(os.path.join(output_path, "config.yaml"), config)
    logger.info("ArborGraph completed successfully. Data saved to %s", output_path)


if __name__ == "__main__":
    main()
