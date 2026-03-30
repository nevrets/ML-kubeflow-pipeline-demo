"""
Multi Repository main branch download
Download Path args.root
"""

import argparse
import os
import time
from pathlib import Path

import lakefs_client
from lakefs_client import models
from lakefs_client.client import LakeFSClient
from loguru import logger
from tqdm import tqdm

LAKEFS_ACCESS_KEY_ID = os.environ["LAKEFS_ACCESS_KEY_ID"]
LAKEFS_SECRET_ACCESS_KEY = os.environ["LAKEFS_SECRET_ACCESS_KEY"]
LAKEFS_URL = os.environ["LAKEFS_URL"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/data/nevret")  ## 마운트되는 폴더경로 잡아줘야함
    parser.add_argument("--repo", default="demo-iris", type=str)
    parser.add_argument("--date", default="2025-04-08-104352", type=str, help="YYYY-MM-DD")

    args = parser.parse_args()

    # Setting Lakefs Config
    configuration = lakefs_client.Configuration()
    configuration.username = LAKEFS_ACCESS_KEY_ID
    configuration.password = LAKEFS_SECRET_ACCESS_KEY
    configuration.host = LAKEFS_URL

    client = LakeFSClient(configuration)

    # Check download folder
    datasets_save_path = os.path.join(args.root)
    os.makedirs(datasets_save_path, exist_ok=True)

    repo_list = [args.repo]
    logger.info(f"Repo list > {repo_list}")
    pre = time.time()

    def get_all_obj(repo, branch, prefix):
        obj = []
        offset = ""
        while True:
            obj_list = client.objects.list_objects(repo, branch, after=offset, prefix=prefix)
            for i in obj_list["results"]:
                obj.append(i["path"])
            if obj_list["pagination"]["has_more"] == True:
                offset = obj_list["pagination"]["next_offset"]
            else:
                break

        return obj

    prefix = args.date

    for repo in repo_list:
        # 각 repository 의 Main 브랜치만 다운로드
        obj_list = get_all_obj(repo, "main", prefix=prefix)
        download_list = obj_list
        # download_list = []
        # if args.sequence_length is not None:
        #     for i in obj_list:
        #         if f"sequence_length_{args.sequence_length}" in i:
        #             download_list.append(i)
        # else:
        #     download_list = obj_list
        logger.info(f"{repo}, {len(download_list)} file Loading...")
        for obj in tqdm(
            download_list, total=len(download_list), desc="Downloading", ascii=" =", miniters=1000, leave=True
        ):
            path = Path(obj)
            save_path = os.path.join(datasets_save_path, path.name)    # path.parent.name
            if not os.path.isdir(os.path.dirname(save_path)):
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
            if not os.path.isfile(save_path):
                f = client.objects.get_object(repo, "main", obj)
                with open(save_path, "wb") as fq:
                    fq.write(f.read())

    logger.info(f"Download Time : {((time.time() - pre) / 1000)} s")
    logger.info(os.listdir('/mnt/preprocessed'))
    # logger.info(os.listdir('/mnt/preprocessed/preprocessed/2025-04-08-104352'))
