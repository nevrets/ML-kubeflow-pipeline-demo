import argparse
import json
import os

import mlflow
from loguru import logger
from mlflow.tracking import MlflowClient

if __name__ == "__main__":
    argparse.ArgumentParser()
    parser = argparse.ArgumentParser()
    parser.add_argument("--seq", type=int, default=8, help="Sequence")
    parser.add_argument("--resample", type=int, default=300, help="Resample")
    parser.add_argument("--pad", type=int, default=0, help="Pad")
    parser.add_argument("--stride", type=int, default=1, help="Stride")

    parser.add_argument("--save_path", type=str, help="Model save path")
    args = parser.parse_args()

    client = MlflowClient()

    model_name = f"Pre-training_Seq{args.seq}_Resample{args.resample}_Pad{args.pad}_Stride{args.stride}"
    model_name = "Pre-training_Seq16_Resample300_Pad0_Stride3"
    production_info = client.get_latest_versions(name=model_name, stages=["Production"])
    if len(production_info) != 0:
        production_run_info = production_info[0]
        logger.info(f"---------------------------Deployments Model Information-------------------------------")
        logger.info(
            f"name : {production_run_info.name}  |  version : {production_run_info.version}  |  run_id : {production_run_info.run_id}"
        )
        pretrain_loss = mlflow.get_run(production_run_info.run_id).data.metrics["val_loss"]

        logger.info(f"Production model file downloading...")

        result_path = mlflow.artifacts.download_artifacts(
            run_id=production_run_info.run_id,
            artifact_path="checkpoints/model_best.pth",
            dst_path=args.save_path,
        )
        logger.info(f"Model file download finish... {result_path}")
        output = {
            "name": production_run_info.name,
            "version": production_run_info.version,
            "run_id": production_run_info.run_id,
            "pretrain_loss": pretrain_loss,
            "path": result_path,
        }
        logger.info(f"Production model information : {output}")
        with open(os.path.join(args.save_path, "info.json"), "w") as f:
            json.dump(output, f, indent=4)
    else:
        logger.error("Production model not found...")
