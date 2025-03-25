import os

cwd = os.getcwd()


def get_db_path():
    """
    Standard db path
    """
    vision_model = os.environ["VISION_MODEL"].replace(":", "_")
    fallback_model = os.environ["MODEL"].replace(":", "_")

    return f"{cwd}/src/data/db/{vision_model}-{fallback_model}"
