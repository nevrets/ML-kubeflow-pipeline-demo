import argparse
import json
import os
import datetime
from pathlib import Path

import mlflow
from loguru import logger
from mlflow.entities import ViewType
from mlflow.tracking.client import MlflowClient


def search_filter_model(experiment_name: str, filter: str, order_by: str) -> str:
    results = mlflow.search_runs(
        experiment_names=[experiment_name],
        order_by=[f'metrics."{filter}" {order_by}'],
        run_view_type=ViewType.ACTIVE_ONLY,
        output_format="list",
    )
    return results[0]


def search_filter_model_based_model_name(model_name: str, filter: str) -> str:
    results = mlflow.search_registered_models(filter_string=f"name='{model_name}'")
    train_list = results[0].latest_versions
    for i in train_list:
        info = mlflow.get_run(i.run_id)
        print(info.data.metrics[filter])

    return results[0]


def model_register(filterd_run_info, name):
    client = MlflowClient()
    update_info = False
    
    try:
        # 필터링된 모델 정보(가장 좋은 성능의 모델) 가져오기
        latest_run_info = filterd_run_info.info
        latest_accuracy = filterd_run_info.data.metrics.get('accuracy', 0.0)
        logger.info(f"Get filtered model information... {latest_run_info.run_id}, accuracy: {latest_accuracy}")

        # 현재 Production 모델 정보 가져오기
        try:
            production_info = client.get_latest_versions(name=name, stages=["Production"])
            logger.info("Found existing model in registry")
        except:
            logger.info(f"No production model found, creating new model: {name}")
            client.create_registered_model(name=name)
            production_info = []

        # Production 모델이 있는 경우
        if len(production_info) != 0:
            production_run_info = production_info[0]
            production_run = mlflow.get_run(production_run_info.run_id)
            production_accuracy = production_run.data.metrics.get('accuracy', 0.0)
            logger.info(f"Current production model: {production_run_info.run_id}, accuracy: {production_accuracy}")

            # 현재 Production 모델과 필터링된 모델이 같은 경우
            if latest_run_info.run_id == production_run_info.run_id:
                logger.info("No model update needed - same version already in production")
                logger.info(
                    f"Current production model: name={production_run_info.name}, version={production_run_info.version}, run_id={production_run_info.run_id}, accuracy={production_accuracy}"
                )
            # 현재 Production 모델의 accuracy가 더 높은 경우
            elif latest_accuracy <= production_accuracy:
                logger.info(f"No model update needed - new accuracy ({latest_accuracy})")
                logger.info(
                    f"Keeping current production model: name={production_run_info.name}, version={production_run_info.version}, run_id={production_run_info.run_id}, accuracy={production_accuracy}"
                )
            else:
                # 새 버전으로 업데이트 - accuracy가 더 좋은 경우에만
                latest_model_info = client.search_model_versions(filter_string=f"run_id='{latest_run_info.run_id}'")
                if not latest_model_info:
                    logger.info(f"Registering new model version from run {latest_run_info.run_id}")
                    client.create_model_version(name=name, source=f"runs:/{latest_run_info.run_id}/model", run_id=latest_run_info.run_id)
                    latest_model_info = client.search_model_versions(filter_string=f"run_id='{latest_run_info.run_id}'")

                update_model_info = client.transition_model_version_stage(
                    name=name,
                    version=latest_model_info[0].version,
                    stage="Production",
                    archive_existing_versions=True,
                )
                logger.info(f"Model updated to production with better accuracy: {latest_accuracy} > {production_accuracy}")
                logger.info(
                    f"New production model: name={update_model_info.name}, version={update_model_info.version}, run_id={update_model_info.run_id}, accuracy={latest_accuracy}"
                )
                update_info = True

        else:
            # Production 모델이 없는 경우 새로 등록
            logger.info(f"Registering first model version from run {latest_run_info.run_id}")
            client.create_model_version(name=name, source=f"runs:/{latest_run_info.run_id}/model", run_id=latest_run_info.run_id)
            latest_model_info = client.search_model_versions(filter_string=f"run_id='{latest_run_info.run_id}'")

            update_model_info = client.transition_model_version_stage(
                name=name,
                version=latest_model_info[0].version,
                stage="Production",
            )
            logger.info("First model version set to production")
            logger.info(
                f"Production model: name={update_model_info.name}, version={update_model_info.version}, run_id={update_model_info.run_id}, accuracy={latest_accuracy}"
            )
            update_info = True

    except Exception as e:
        logger.error(f"Error during model registration: {str(e)}")
        update_info = False
        
    finally:
        # 항상 update.json 파일 생성
        result = {
            "updated": update_info,
            "timestamp": datetime.datetime.now().isoformat()
        }
        os.makedirs("/workspace", exist_ok=True)
        with open("/workspace/update.json", "w") as f:
            json.dump(result, f, indent=4)
        logger.info(f"Created update.json with status: {update_info}")




if __name__ == "__main__":
    assert (
        os.getenv("MLFLOW_TRACKING_URI", None) is not None
    ), "MLFLOW_TRACKING_URI is not set. Check environment."

    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment_name", type=str, default="[DEMO]Iris_Training")
    parser.add_argument("--model_name", type=str, default="[DEMO]Iris_Training")
    parser.add_argument("--filter", type=str, default="accuracy")
    parser.add_argument("--order_by", type=str, default="DESC", choices=["ASC", "DESC"])
    parser.add_argument("--run_info", type=str)
    
    args = parser.parse_args()

    experiment_name = args.experiment_name
    model_name = args.model_name

    logger.info("Searching model...")
    logger.info(
        f"Experiment name : {args.experiment_name}  | Model name : {model_name}  | Metric : {args.filter} | Order by : {args.order_by}"
    )
    # res = search_filter_model_based_model_name(model_name=model_name, filter=args.filter)
    
    # filter 기준 모델 조회 - 전체 모델에서 args.filter 기준으로 지표가 가장 높은 모델
    filterd_run_info = search_filter_model(
        experiment_name=experiment_name, filter=args.filter, order_by=args.order_by
    )
    logger.info(f"Model searching done... {args.filter} = {filterd_run_info.data.metrics[args.filter]}")
    
    # 모델 등록
    model_register(filterd_run_info=filterd_run_info, name=model_name)

    exit(0)
