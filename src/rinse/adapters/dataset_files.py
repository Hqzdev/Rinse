from pathlib import Path

from rinse.domain.value_objects import DatasetFormat, DatasetReference


class UnsupportedDatasetFormatError(ValueError):
    pass


class DatasetFileError(ValueError):
    pass


class DatasetFormatDetector:
    def detect(self, reference: DatasetReference) -> DatasetFormat:
        if reference.format is not None:
            return reference.format
        suffix = Path(reference.location).suffix.lower()
        if suffix == ".csv":
            return DatasetFormat.CSV
        if suffix == ".xlsx":
            return DatasetFormat.XLSX
        if suffix == ".json":
            return DatasetFormat.JSON
        raise UnsupportedDatasetFormatError(f"Unsupported dataset format: {reference.location}")


class DatasetPath:
    def resolve(self, reference: DatasetReference) -> Path:
        path = Path(reference.location)
        if not path.exists():
            raise DatasetFileError(f"Dataset file does not exist: {reference.location}")
        if not path.is_file():
            raise DatasetFileError(f"Dataset reference is not a file: {reference.location}")
        return path
