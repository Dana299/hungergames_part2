import csv
import io
import zipfile
from typing import List


def get_lines_from_csv(zip_file: bytes) -> List[str]:
    """Get list of lines from csv file."""

    with zipfile.ZipFile(io.BytesIO(zip_file), 'r') as zip_ref:
        # search CSV files in archive
        csv_files = [file for file in zip_ref.namelist() if file.endswith('.csv')]
        if len(csv_files) == 0:
            raise ValueError('No CSV file found in the zip archive.')

        csv_file = csv_files[0]

        lines = []

        with zip_ref.open(csv_file) as csv_data:
            csv_reader = csv.reader(io.TextIOWrapper(csv_data, 'utf-8'))
            for row in csv_reader:
                lines.append(row[0])

    return lines