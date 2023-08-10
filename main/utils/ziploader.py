import csv
import io
import uuid
import zipfile
from typing import List

from main import app
from main.service import exceptions


def allowed_file(filename: str):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def make_uuid_filename(filename: str) -> str:
    """Extracts file extension from the given filename and make random uuid4 name."""
    return "{}.{}".format(str(uuid.uuid4()), filename.split('.')[-1])


def get_lines_from_csv(zip_file: str) -> List[str]:
    """Get list of lines from csv file."""

    with zipfile.ZipFile(file=zip_file, mode='r') as zip_ref:
        # search CSV files in archive
        csv_files = [file for file in zip_ref.namelist() if file.endswith('.csv')]
        if len(csv_files) == 0:
            raise exceptions.NoCSVFileError('No CSV file found in the zip archive.')

        csv_file = csv_files[0]

        lines = []

        with zip_ref.open(csv_file) as csv_data:
            csv_reader = csv.reader(io.TextIOWrapper(csv_data, 'utf-8'))
            for row in csv_reader:
                lines.append(row[0])

    return lines
