import os
import pandas as pd
import argparse

from loguru import logger


def main(args):    
    data = pd.read_csv(os.path.join(args.data_path, 'iris.csv'))
    logger.info(f"Total data shape: {data.shape}")
    
    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)
        
    data.to_csv(os.path.join(args.output_path, 'iris.csv'), index=False)
    

    

if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--data_path', type=str, help="Input data path")
    argument_parser.add_argument('--output_path', type=str, help="Output data path")

    args = argument_parser.parse_args()

    main(args)