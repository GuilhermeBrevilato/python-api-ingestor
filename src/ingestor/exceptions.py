class DataPipelineError(Exception):
    def __init__(
            self,
            message: str,
            *,
            source: str,
    ) -> None:
        super().__init__(message)
        self.source = source

class ExtractionError(DataPipelineError):
    pass

class StorageError(DataPipelineError):
    pass