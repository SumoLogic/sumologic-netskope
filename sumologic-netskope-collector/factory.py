import importlib
import sys
from logger import get_logger

class BaseFactory(object):
    INIT_FILE = "__init__.py"

    @classmethod
    def load_class(cls, full_class_string):
        """
            dynamically load a class from a string
        """

        #  using importlib https://docs.python.org/3/library/importlib.html find_spec not working in 2.7
        log = get_logger(__name__)
        try:
            class_data = full_class_string.split(".")
            module_path = ".".join(class_data[:-1])
            class_str = class_data[-1]
            module = importlib.import_module(module_path)
            return getattr(module, class_str)
        except Exception as e:
            t, v, tb = sys.exc_info()
            log.error(f"Unable to import Module {full_class_string} Error: {e} Traceback: {tb}")
            raise t(v).with_traceback(tb)


class ProviderFactory(BaseFactory):

    provider_map = {
        # "aws": AWSProvider,
        # "azure": AzureProvider,
        # "gcp": GCPProvider,
        "onprem": "onprem.OnPremProvider"
    }

    @classmethod
    def get_provider(cls, provider_name, *args, **kwargs):

        if provider_name in cls.provider_map:
            module_class = cls.load_class(cls.provider_map[provider_name])
            module_instance = module_class(*args, **kwargs)
            return module_instance
        else:
            raise Exception(f"{provider_name} provider not found")

    @classmethod
    def add_provider(cls, provider_name, provider_class):
        cls.provider_map[provider_name] = provider_class


class OutputHandlerFactory(BaseFactory):

    handlers = {
        "HTTP": "outputhandlers.HTTPHandler",
        "CONSOLE": "outputhandlers.HTTPHandler",
    }

    @classmethod
    def get_handler(cls, handler_type, *args, **kwargs):

        if handler_type in cls.handlers:
            module_class = cls.load_class(cls.handlers[handler_type])
            module_instance = module_class(*args, **kwargs)
            return module_instance
        else:
            raise Exception(f"Invalid OUTPUTHANDLER {handler_type}")


