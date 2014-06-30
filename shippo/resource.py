import urllib
import warnings
import sys

from shippo import api_requestor, error, util


def convert_to_shippo_object(resp, auth):
    types = {'address': Address}

    if isinstance(resp, list):
        return [convert_to_shippo_object(i, auth) for i in resp]
    elif isinstance(resp, dict) and not isinstance(resp, ShippoObject):
        resp = resp.copy()
        klass_name = resp.get('object')
        if isinstance(klass_name, basestring):
            klass = types.get(klass_name, ShippoObject)
        else:
            klass = ShippoObject
        return klass.construct_from(resp, auth)
    else:
        return resp


class ShippoObject(dict):
    def __init__(self, id=None, auth=None, **params):
        super(ShippoObject, self).__init__()

        self._unsaved_values = set()
        self._transient_values = set()

        self._retrieve_params = params
        self._previous_metadata = None

        object.__setattr__(self, 'auth', auth)

        if id:
            self['id'] = id

    def __setattr__(self, k, v):
        if k[0] == '_' or k in self.__dict__:
            return super(ShippoObject, self).__setattr__(k, v)
        else:
            self[k] = v

    def __getattr__(self, k):
        if k[0] == '_':
            raise AttributeError(k)

        try:
            return self[k]
        except KeyError, err:
            raise AttributeError(*err.args)

    def __setitem__(self, k, v):
        if v == "":
            raise ValueError(
                "You cannot set %s to an empty string. "
                "We interpret empty strings as None in requests."
                "You may set %s.%s = None to delete the property" % (
                    k, str(self), k))

        super(ShippoObject, self).__setitem__(k, v)

        # Allows for unpickling in Python 3.x
        if not hasattr(self, '_unsaved_values'):
            self._unsaved_values = set()

        self._unsaved_values.add(k)

    def __getitem__(self, k):
        try:
            return super(ShippoObject, self).__getitem__(k)
        except KeyError, err:
            if k in self._transient_values:
                raise KeyError(
                    "%r.  HINT: The %r attribute was set in the past."
                    "It was then wiped when refreshing the object with "
                    "the result returned by Shippo's API, probably as a "
                    "result of a save().  The attributes currently "
                    "available on this object are: %s" %
                    (k, k, ', '.join(self.keys())))
            else:
                raise err

    def __delitem__(self, k):
        raise TypeError(
            "You cannot delete attributes on a ShippoObject. "
            "To unset a property, set it to None.")

    @classmethod
    def construct_from(cls, values, auth):
        instance = cls(values.get('id'), auth)
        instance.refresh_from(values, auth)
        return instance

    def refresh_from(self, values, auth=None, partial=False):
        self.auth = auth or getattr(values, 'auth', None)

        # Wipe old state before setting new.
        if partial:
            self._unsaved_values = (self._unsaved_values - set(values))
        else:
            removed = set(self.keys()) - set(values)
            self._transient_values = self._transient_values | removed
            self._unsaved_values = set()

            self.clear()

        self._transient_values = self._transient_values - set(values)

        for k, v in values.iteritems():
            super(ShippoObject, self).__setitem__(
                k, convert_to_shippo_object(v, auth))

        self._previous_metadata = values.get('metadata')

    def request(self, method, url, params=None):
        if params is None:
            params = self._retrieve_params

        requestor = api_requestor.APIRequestor(self.auth)
        response, auth = requestor.request(method, url, params)

        return convert_to_shippo_object(response, auth)

    def __repr__(self):
        ident_parts = [type(self).__name__]

        if isinstance(self.get('object'), basestring):
            ident_parts.append(self.get('object'))

        if isinstance(self.get('id'), basestring):
            ident_parts.append('id=%s' % (self.get('id'),))

        unicode_repr = '<%s at %s> JSON: %s' % (
            ' '.join(ident_parts), hex(id(self)), str(self))

        if sys.version_info[0] < 3:
            return unicode_repr.encode('utf-8')
        else:
            return unicode_repr

    def __str__(self):
        return util.json.dumps(self, sort_keys=True, indent=2)

    @property
    def shippo_id(self):
        return self.id


class APIResource(ShippoObject):

    @classmethod
    def retrieve(cls, id, auth=None, **params):
        instance = cls(id, auth, **params)
        instance.refresh()
        return instance

    def refresh(self):
        self.refresh_from(self.request('get', self.instance_url()))
        return self

    @classmethod
    def class_name(cls):
        if cls == APIResource:
            raise NotImplementedError(
                'APIResource is an abstract class.  You should perform '
                'actions on its subclasses (e.g. Address, Parcel)')
        return str(urllib.quote_plus(cls.__name__.lower()))

    @classmethod
    def class_url(cls):
        cls_name = cls.class_name()
        return "/v1/%ss" % (cls_name,)

    def instance_url(self):
        id = self.get('id')
        if not id:
            raise error.InvalidRequestError(
                'Could not determine which URL to request: %s instance '
                'has invalid ID: %r' % (type(self).__name__, id), 'id')
        id = util.utf8(id)
        base = self.class_url()
        extn = urllib.quote_plus(id)
        return "%s/%s" % (base, extn)


class ListObject(ShippoObject):

    def all(self, **params):
        return self.request('get', self['url'], params)

    def create(self, **params):
        return self.request('post', self['url'], params)

    def retrieve(self, id, **params):
        base = self.get('url')
        id = util.utf8(id)
        extn = urllib.quote_plus(id)
        url = "%s/%s" % (base, extn)

        return self.request('get', url, params)


# Classes of API operations


class ListableAPIResource(APIResource):

    @classmethod
    def all(cls, auth=None, **params):
        requestor = api_requestor.APIRequestor(auth)
        url = cls.class_url()
        response, auth = requestor.request('get', url, params)
        return convert_to_shippo_object(response, auth)


class CreateableAPIResource(APIResource):

    @classmethod
    def create(cls, auth=None, **params):
        requestor = api_requestor.APIRequestor(auth)
        url = cls.class_url()
        response, content = requestor.request('post', url, params)
        return convert_to_shippo_object(response, content)

# API objects


class Address(CreateableAPIResource, ListableAPIResource):
    def validate(self, **params):
        url = self.instance_url() + '/validate'
