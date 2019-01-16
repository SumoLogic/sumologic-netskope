from abc import ABCMeta, abstractmethod


class Provider(metaclass=ABCMeta):

    def __init__(self, *args, **kwargs):
        self.setup(*args, **kwargs)

    def get_storage(self, storage_type, *args, **kwargs):
        storage_type_map = {
            "keyvalue": self.get_kvstorage
        }

        if storage_type in storage_type_map:
            instance = storage_type_map[storage_type](*args, **kwargs)
            return instance
        else:
            raise Exception("%s storage_type not found" % storage_type)


    @abstractmethod
    def get_kvstorage(self, *args, **kwargs):
        pass

    @abstractmethod
    def setup(*args, **kwargs):
        pass


class KeyValueStorage(metaclass=ABCMeta):
    #Todo support atomic + updates + batch get/set

    def __init__(self, *args, **kwargs):
        self.setup(*args, **kwargs)

    @abstractmethod
    def setup(self, *args, **kwargs):
        pass

    @abstractmethod
    def get(self, key):
        pass

    @abstractmethod
    def set(self, key, value):
        pass

    @abstractmethod
    def delete(self, key):
        pass

    @abstractmethod
    def has_key(self, key):
        pass

    @abstractmethod
    def destroy(self):
        pass
