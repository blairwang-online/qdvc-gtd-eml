"""
Filesystem helpers: creating the folder structure, listing EML files, and
locating a single EML by name across all folders.
"""

import os

from . import config


def ensure_folders(base_dir):
    """
    Create the 5 GTD folders if they don't exist.

    Example:
        ensure_folders("/home/me/gtd")
        # -> creates /home/me/gtd/01-input, .../02-triage, ... if missing
    """
    for folder in config.ALL_DIRS:
        os.makedirs(os.path.join(base_dir, folder), exist_ok=True)


def list_eml_files(base_dir, folder):
    """
    Return a sorted list of .eml filenames (not full paths) in a given folder.

    Example:
        list_eml_files("/home/me/gtd", "02-triage")
        # -> ["2026-06-12-meeting-minutes.eml", "2026-06-13-update.eml"]
    """
    folder_path = os.path.join(base_dir, folder)
    if not os.path.isdir(folder_path):
        return []
    return sorted(
        f for f in os.listdir(folder_path)
        if f.lower().endswith(".eml")
        and os.path.isfile(os.path.join(folder_path, f))
    )


def all_existing_filenames(base_dir):
    """
    Return a set of every .eml filename present across all 5 folders.

    Example:
        all_existing_filenames("/home/me/gtd")
        # -> {"2026-06-12-meeting.eml", "2026-06-13-update.eml"}
    """
    names = set()
    for folder in config.ALL_DIRS:
        names.update(list_eml_files(base_dir, folder))
    return names


def find_eml(base_dir, filename):
    """
    Search the 5 GTD folders for an .eml file and return its full path, or None.
    A ".eml" extension is appended if the user omitted it.

    Example:
        find_eml("/home/me/gtd-eml", "2026-06-03-project-pudding.eml")
        # -> "/home/me/gtd-eml/03-actionable/2026-06-03-project-pudding.eml"
    """
    if not filename.lower().endswith(".eml"):
        filename += ".eml"
    for folder in config.ALL_DIRS:
        candidate = os.path.join(base_dir, folder, filename)
        if os.path.isfile(candidate):
            return candidate
    return None
