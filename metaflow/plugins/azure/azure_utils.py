import metaflow.plugins.azure.azure_python_version_check
from metaflow.metaflow_config import AZURE_STORAGE_SHARED_ACCESS_SIGNATURE

from metaflow.datastore.azure_exceptions import (
    MetaflowAzureAuthenticationError,
    MetaflowAzureResourceError,
)
from metaflow.exception import MetaflowInternalError


try:

    # Python 3.6 would print lots of warnings about deprecated cryptography usage when importing Azure modules
    import warnings

    warnings.filterwarnings("ignore")
    from azure.identity import DefaultAzureCredential
    from azure.core.exceptions import (
        ClientAuthenticationError,
        ResourceNotFoundError,
        ResourceExistsError,
        AzureError,
    )

except ImportError:
    raise MetaflowInternalError(
        msg="Please ensure azure-identity and azure-storage-blob Python packages are installed"
    )


def parse_azure_full_path(blob_full_uri):
    """
    Parse an Azure Blob storage path str into a tuple (container_name, blob).

    Expected format is: <container_name>/<blob>

    This is sometimes used to parse an Azure sys root, in which case:

    - <container_name> is the Azure Blob Storage container name
    - <blob> is effectively a blob_prefix, a subpath within the container to which blobs will live

    We take a strict validation approach, doing no implicit string manipulations on
    the user's behalf.  Path manipulations by themselves are complicated enough without
    adding magic.

    We provide clear error messages so the user knows exactly how to fix any validation error.
    """
    if blob_full_uri.endswith("/"):
        raise ValueError("sysroot may not end with slash (got %s)" % blob_full_uri)
    if blob_full_uri.startswith("/"):
        raise ValueError("sysroot may not start with slash (got %s)" % blob_full_uri)
    if "//" in blob_full_uri:
        raise ValueError(
            "sysroot may not contain any consecutive slashes (got %s)" % blob_full_uri
        )
    parts = blob_full_uri.split("/", 1)
    container_name = parts[0]
    if container_name == "":
        raise ValueError(
            "Container name part of sysroot may not be empty (tried to parse %s)"
            % (blob_full_uri,)
        )
    if len(parts) == 1:
        blob_name = None
    else:
        blob_name = parts[1]

    return container_name, blob_name


def process_exception(e):
    """
    Translate errors to Metaflow errors for standardized messaging. The intent is that all
    Azure Blob Storage integration logic should send any errors to this function for
    translation.

    We explicitly EXCLUDE executor related errors here.  See handle_executor_exceptions
    """
    if isinstance(e, ClientAuthenticationError):
        raise MetaflowAzureAuthenticationError(msg=str(e).splitlines()[-1])
    elif isinstance(e, (ResourceNotFoundError, ResourceExistsError)):
        raise MetaflowAzureResourceError(msg=str(e))
    elif isinstance(e, AzureError):  # this is the base class for all Azure SDK errors
        raise MetaflowInternalError(msg="Azure error: %s" % (str(e)))
    else:
        raise MetaflowInternalError(msg=str(e))


def handle_exceptions(func):
    """This is a decorator leveraging the logic from process_exception()"""

    def inner_function(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            process_exception(e)

    return inner_function


class CacheableDefaultAzureCredential(DefaultAzureCredential):
    def __init__(self, *args, **kwargs):
        super(CacheableDefaultAzureCredential, self).__init__(*args, **kwargs)
        self._hash_code = hash((args, tuple(sorted(kwargs.items()))))

    def __hash__(self):
        return self._hash_code

    def __eq__(self, other):
        return hash(self) == hash(other)


def get_azure_storage_access_key():
    """Wrapping into a function to ease testing"""
    return AZURE_STORAGE_SHARED_ACCESS_SIGNATURE