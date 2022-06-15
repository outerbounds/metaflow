import sys
from metaflow.exception import MetaflowInternalError

if sys.version_info[:2] < (3, 6):
    raise MetaflowInternalError(
        msg="Metaflow may only use Azure Blob Storage with Python 3.6 or newer"
    )
