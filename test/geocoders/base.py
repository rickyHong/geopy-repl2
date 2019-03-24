import unittest
from contextlib import ExitStack
from unittest.mock import patch, sentinel

import geopy.geocoders
import geopy.geocoders.base
from geopy.exc import GeocoderNotFound, GeocoderQueryError
from geopy.geocoders import GoogleV3, get_geocoder_for_service
from geopy.geocoders.base import Geocoder
from geopy.point import Point


class GetGeocoderTestCase(unittest.TestCase):

    def test_get_geocoder_for_service(self):
        self.assertEqual(get_geocoder_for_service("google"), GoogleV3)
        self.assertEqual(get_geocoder_for_service("googlev3"), GoogleV3)

    def test_get_geocoder_for_service_raises_for_unknown(self):
        with self.assertRaises(GeocoderNotFound):
            get_geocoder_for_service("")


class GeocoderTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.geocoder = Geocoder()

    def test_init_with_args(self):
        format_string = '%s Los Angeles, CA USA'
        scheme = 'http'
        timeout = 942
        proxies = {'https': '192.0.2.0'}
        user_agent = 'test app'
        ssl_context = sentinel.some_ssl_context

        geocoder = Geocoder(
            format_string=format_string,
            scheme=scheme,
            timeout=timeout,
            proxies=proxies,
            user_agent=user_agent,
            ssl_context=ssl_context,
        )
        for attr in ('format_string', 'scheme', 'timeout', 'proxies',
                     'ssl_context'):
            self.assertEqual(locals()[attr], getattr(geocoder, attr))
        self.assertEqual(user_agent, geocoder.headers['User-Agent'])

    def test_init_with_defaults(self):
        attr_to_option = {
            'format_string': 'default_format_string',
            'scheme': 'default_scheme',
            'timeout': 'default_timeout',
            'proxies': 'default_proxies',
            'ssl_context': 'default_ssl_context',
        }

        geocoder = Geocoder()
        for geocoder_attr, options_attr in attr_to_option.items():
            self.assertEqual(getattr(geopy.geocoders.options, options_attr),
                             getattr(geocoder, geocoder_attr))
        self.assertEqual(geopy.geocoders.options.default_user_agent,
                         geocoder.headers['User-Agent'])

    @patch.object(geopy.geocoders.options, 'default_proxies', {'https': '192.0.2.0'})
    @patch.object(geopy.geocoders.options, 'default_timeout', 10)
    @patch.object(geopy.geocoders.options, 'default_ssl_context',
                  sentinel.some_ssl_context)
    def test_init_with_none_overrides_default(self):
        geocoder = Geocoder(proxies=None, timeout=None, ssl_context=None)
        self.assertIsNone(geocoder.proxies)
        self.assertIsNone(geocoder.timeout)
        self.assertIsNone(geocoder.ssl_context)

    @patch.object(geopy.geocoders.options, 'default_user_agent',
                  'mocked_user_agent/0.0.0')
    def test_user_agent_default(self):
        geocoder = Geocoder()
        self.assertEqual(geocoder.headers['User-Agent'],
                         'mocked_user_agent/0.0.0')

    def test_user_agent_custom(self):
        geocoder = Geocoder(
            user_agent='my_user_agent/1.0'
        )
        self.assertEqual(geocoder.headers['User-Agent'], 'my_user_agent/1.0')

    @patch.object(geopy.geocoders.options, 'default_timeout', 12)
    def test_call_geocoder_timeout(self):
        url = 'spam://ham/eggs'

        g = Geocoder()
        self.assertEqual(g.timeout, 12)

        with ExitStack() as stack:
            mock_get_json = stack.enter_context(patch.object(g.adapter, 'get_json'))

            g._call_geocoder(url)
            args, kwargs = mock_get_json.call_args
            self.assertEqual(kwargs['timeout'], 12)

            g._call_geocoder(url, timeout=7)
            args, kwargs = mock_get_json.call_args
            self.assertEqual(kwargs['timeout'], 7)

            g._call_geocoder(url, timeout=None)
            args, kwargs = mock_get_json.call_args
            self.assertIsNone(kwargs['timeout'])

    def test_ssl_context(self):
        with ExitStack() as stack:
            mock_adapter = stack.enter_context(
                patch.object(geopy.geocoders.base.options, 'adapter_factory')
            )

            for ssl_context in (None, sentinel.some_ssl_context):
                Geocoder(ssl_context=ssl_context)
                args, kwargs = mock_adapter.call_args
                self.assertIs(kwargs['ssl_context'], ssl_context)


class GeocoderPointCoercionTestCase(unittest.TestCase):
    coordinates = (40.74113, -73.989656)
    coordinates_str = "40.74113,-73.989656"
    coordinates_address = "175 5th Avenue, NYC, USA"

    def setUp(self):
        self.method = Geocoder._coerce_point_to_string

    def test_point(self):
        latlon = self.method(Point(*self.coordinates))
        self.assertEqual(latlon, self.coordinates_str)

    def test_tuple_of_floats(self):
        latlon = self.method(self.coordinates)
        self.assertEqual(latlon, self.coordinates_str)

    def test_string(self):
        latlon = self.method(self.coordinates_str)
        self.assertEqual(latlon, self.coordinates_str)

    def test_string_is_trimmed(self):
        coordinates_str_spaces = "  %s  ,  %s  " % self.coordinates
        latlon = self.method(coordinates_str_spaces)
        self.assertEqual(latlon, self.coordinates_str)

    def test_output_format_is_respected(self):
        expected = "  %s  %s  " % self.coordinates[::-1]
        lonlat = self.method(self.coordinates_str, "  %(lon)s  %(lat)s  ")
        self.assertEqual(lonlat, expected)

    def test_address(self):
        with self.assertRaises(ValueError):
            self.method(self.coordinates_address)


class GeocoderFormatBoundingBoxTestCase(unittest.TestCase):

    def setUp(self):
        self.method = Geocoder._format_bounding_box

    def test_string_raises(self):
        with self.assertRaises(GeocoderQueryError):
            self.method("5,5,5,5")

    def test_list_of_1_raises(self):
        with self.assertRaises(GeocoderQueryError):
            self.method([5])

    # TODO maybe raise for `[5, 5]` too?

    def test_list_of_3_raises(self):
        with self.assertRaises(GeocoderQueryError):
            self.method([5, 5, 5])

    def test_list_of_4_raises(self):
        with self.assertRaises(GeocoderQueryError):
            self.method([5, 5, 5, 5])

    def test_list_of_5_raises(self):
        with self.assertRaises(GeocoderQueryError):
            self.method([5, 5, 5, 5, 5])

    def test_points(self):
        bbox = self.method([Point(50, 160), Point(30, 170)])
        self.assertEqual(bbox, "30.0,160.0,50.0,170.0")

    def test_lists(self):
        bbox = self.method([[50, 160], [30, 170]])
        self.assertEqual(bbox, "30.0,160.0,50.0,170.0")
        bbox = self.method([["50", "160"], ["30", "170"]])
        self.assertEqual(bbox, "30.0,160.0,50.0,170.0")

    def test_strings(self):
        bbox = self.method(["50, 160", "30,170"])
        self.assertEqual(bbox, "30.0,160.0,50.0,170.0")

    def test_output_format(self):
        bbox = self.method([Point(50, 160), Point(30, 170)],
                           " %(lon2)s|%(lat2)s -- %(lat1)s|%(lon1)s ")
        self.assertEqual(bbox, " 170.0|50.0 -- 30.0|160.0 ")
