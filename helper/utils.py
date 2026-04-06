import json
import os
import time


try:
    import loguru
    logger = loguru.logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def install_folders(folders_paths, name=None):
    logger.info(f"Installing {name if name is not None else 'folders'}...")
    for source_folder_path in folders_paths:
        install_folder(source_folder_path, folders_paths[source_folder_path], name)


def install_files(files_paths, name=None):
    logger.info(f"Installing {name if name is not None else 'files'}...")
    for source_file_path in files_paths:
        install_file(source_file_path, files_paths[source_file_path], name) 


def install_file(source_path, destination_path, name=None):
    source_path = os.path.expanduser(source_path)
    destination_path = os.path.expanduser(destination_path)
    # check if file exists
    if os.path.exists(destination_path) or os.path.islink(destination_path):
        logger.info(f"File {destination_path} already exists.")
        # check if it is a symlink
        if os.path.islink(destination_path):
            logger.info(f"File {destination_path} is already linked.")
            os.unlink(destination_path)
            os.symlink(source_path, destination_path)
        else:
            logger.info(f"Backing up existing file {destination_path}.")
            timestamp = int(time.time())
            os.rename(
                destination_path,
                f"{destination_path}.{timestamp}.bak",
            )
            logger.info(
                f"Backed up existing file to {destination_path}.{timestamp}.bak."
            )
            logger.info(f"Linking {source_path} to {destination_path}.")
            os.symlink(source_path, destination_path)
    else:
        # check if parent folder exists
        parent_destination_folder = os.path.dirname(destination_path)
        if not os.path.exists(parent_destination_folder):
            logger.info(f"Creating parent folder {parent_destination_folder}.")
            os.makedirs(parent_destination_folder, exist_ok=True)
        logger.info(f"Linking {source_path} to {destination_path}.")
        os.symlink(source_path, destination_path)
    if name is not None:
        logger.info(f"Installed {name} configuration.")


def install_folder(source_path, destination_path, name=None):
    source_path = os.path.expanduser(source_path)
    destination_path = os.path.expanduser(destination_path)
    # check if folder exists
    if os.path.exists(destination_path):
        logger.info(f"Folder {destination_path} already exists.")
        # check if it is a symlink
        if os.path.islink(destination_path):
            logger.info(f"Folder {destination_path} is already linked.")
            os.unlink(destination_path)
            os.symlink(source_path, destination_path, target_is_directory=True)
        else:
            logger.info(f"Backing up existing folder {destination_path}.")
            timestamp = int(time.time())
            os.rename(
                destination_path,
                f"{destination_path}.{timestamp}.bak",
            )
            logger.info(
                f"Backed up existing folder to {destination_path}.{timestamp}.bak."
            )
            logger.info(f"Linking {source_path} to {destination_path}.")
            os.symlink(source_path, destination_path, target_is_directory=True)
    else:
        # check if parent folder exists
        parent_destination_folder = os.path.dirname(destination_path)
        if not os.path.exists(parent_destination_folder):
            logger.info(f"Creating parent folder {parent_destination_folder}.")
            os.makedirs(parent_destination_folder, exist_ok=True)
        logger.info(f"Linking {source_path} to {destination_path}.")
        os.symlink(source_path, destination_path, target_is_directory=True)
    if name is not None:
        logger.info(f"Installed {name} configuration.")


def install_credentials(credentials, destination_path=os.path.join("~", ".config", "credentials.json")):
    secrets = {}
    logger.info("Installing credentials...")
    for credential in credentials:
        secret = input(f"Enter the value for {credential}: ")
        secrets[credential] = secret
    destination_path = os.path.expanduser(destination_path)
    if os.path.exists(destination_path):
        logger.info(f"Credentials file {destination_path} already exists.")
        timestamp = int(time.time())
        os.rename(
            destination_path,
            f"{destination_path}.{timestamp}.bak",
        )
        # change file permissions of the backup file to read only for the user
        os.chmod(f"{destination_path}.{timestamp}.bak", 0o600)
        logger.info(
            f"Backed up existing credentials file to {destination_path}.{timestamp}.bak."
        )
    json.dump(
        secrets,
        open(destination_path, "w"),
        indent=4,
    )
    logger.info(f"Installed credentials to {destination_path}.")
    # change file permissions to read only for the user
    os.chmod(destination_path, 0o600)


if __name__ == "__main__":
    pass