from aws import AWSProvider
from onprem import OnPremProvider


class ProviderFactory(object):

    provider_map = {
        "aws": AWSProvider,
        # "azure": AzureProvider,
        # "gcp": GCPProvider,
        "onprem": OnPremProvider
    }

    @classmethod
    def get_provider(cls, provider_name, *args, **kwargs):

        if provider_name in cls.provider_map:
            return cls.provider_map[provider_name](*args, **kwargs)
        else:
            raise Exception("%s provider not found" % provider_name)

    @classmethod
    def add_provider(cls, provider_name, provider_class):
        cls.provider_map[provider_name] = provider_class
