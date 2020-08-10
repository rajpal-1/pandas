import os

import pytest

import pandas._testing as tm

from pandas.io.parsers import read_csv


@pytest.fixture
def tips_file(datapath):
    """Path to the tips dataset"""
    return datapath("io", "data", "csv", "tips.csv")


@pytest.fixture
def jsonl_file(datapath):
    """Path to a JSONL dataset"""
    return datapath("io", "parser", "data", "items.jsonl")


@pytest.fixture
def salaries_table(datapath):
    """DataFrame with the salaries dataset"""
    return read_csv(datapath("io", "parser", "data", "salaries.csv"), sep="\t")


@pytest.fixture
def feather_file(datapath):
    return datapath("io", "data", "feather", "feather-0_3_1.feather")


@pytest.fixture
def s3_resource(tips_file, jsonl_file, feather_file):
    """
    Fixture for mocking S3 interaction.

    The primary bucket name is "pandas-test". The following datasets
    are loaded.

    - tips.csv
    - tips.csv.gz
    - tips.csv.bz2
    - items.jsonl

    A private bucket "cant_get_it" is also created. The boto3 s3 resource
    is yielded by the fixture.
    """
    s3fs = pytest.importorskip("s3fs")
    boto3 = pytest.importorskip("boto3")

    with tm.ensure_safe_environment_variables():
        # temporary workaround as moto fails for botocore >= 1.11 otherwise,
        # see https://github.com/spulec/moto/issues/1924 & 1952
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "foobar_key")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "foobar_secret")

        moto = pytest.importorskip("moto")

        test_s3_files = [
            ("tips#1.csv", tips_file),
            ("tips.csv", tips_file),
            ("tips.csv.gz", tips_file + ".gz"),
            ("tips.csv.bz2", tips_file + ".bz2"),
            ("items.jsonl", jsonl_file),
            ("simple_dataset.feather", feather_file),
        ]

        def add_tips_files(bucket_name):
            for s3_key, file_name in test_s3_files:
                with open(file_name, "rb") as f:
                    conn.Bucket(bucket_name).put_object(Key=s3_key, Body=f)

        try:
            import shlex
            import subprocess
            import time

            import requests

            endpoint_uri = "http://127.0.0.1:5555/"

            proc = subprocess.Popen(shlex.split("moto_server s3 -p 5555"))

            timeout = 5
            while timeout > 0:
                try:
                    r = requests.get(endpoint_uri)
                    if r.ok:
                        break
                except Exception:
                    pass
                timeout -= 0.1
                time.sleep(0.1)

            # see gh-16135
            bucket = "pandas-test"
            conn = boto3.resource("s3", endpoint_url=endpoint_uri)

            conn.create_bucket(Bucket=bucket)
            add_tips_files(bucket)

            conn.create_bucket(Bucket="cant_get_it", ACL="private")
            add_tips_files("cant_get_it")
            s3fs.S3FileSystem.clear_instance_cache()
            yield conn
        finally:
            proc.terminate()
            proc.wait()
