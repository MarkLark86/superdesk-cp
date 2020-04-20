
import unittest
import superdesk
import lxml.etree as etree

from pytz import UTC
from datetime import datetime
from unittest.mock import patch, MagicMock, create_autospec

from superdesk.metadata.utils import generate_guid
from superdesk.publish.subscribers import SubscribersService

from cp.output.formatter.jimi import JimiFormatter


subscriber_service = create_autospec(SubscribersService)
subscriber_service.generate_sequence_number.return_value = 100


class JimiFormatterTestCase(unittest.TestCase):

    subscriber = {}
    formatter = JimiFormatter()
    article = {
        '_id': '123',
        'type': 'text',
        'headline': 'Headline',
        'slugline': 'slug',
        'creditline': 'Credit',
        'source': 'Source',
        'ednote': 'Ednote',
        'word_count': 123,
        'abstract': '<p>Abstract</p>',
        'body_html': '<p>Body HTML</p>',
        'keywords': ['Foo bar', 'baz'],
        'anpa_category': [{'name': 'National', 'qcode': 'n'}],
        'subject': [{'name': 'Health', 'qcode': 'h'}, {'name': 'National', 'qcode': 'n'}],
        'urgency': 3,

        'firstcreated': datetime(2020, 4, 1, 11, 13, 12, 25, tzinfo=UTC),
        'versioncreated': datetime(2020, 4, 1, 11, 23, 12, 25, tzinfo=UTC),
        'firstpublished': datetime(2020, 4, 1, 11, 33, 12, 25, tzinfo=UTC),
    }

    def format(self, updates=None):
        article = self.article.copy()
        article.update(updates or {})
        with patch.object(superdesk, 'get_resource_service', return_value=subscriber_service):
            seq, xml_str = self.formatter.format(article, self.subscriber)[0]
        print('xml', xml_str)
        return xml_str

    def get_root(self, xml):
        return etree.fromstring(xml.encode(self.formatter.ENCODING))

    def format_item(self, updates=None):
        xml = self.format(updates)
        root = self.get_root(xml)
        return root.find('ContentItem')

    def test_can_format(self):
        self.assertTrue(self.formatter.can_format('jimi', {}))

    def test_format(self):
        xml = self.format()
        self.assertIn("<?xml version='1.0' encoding='utf-8'?>", xml)
        root = etree.fromstring(xml.encode(self.formatter.ENCODING))

        self.assertEqual('Publish', root.tag)
        self.assertEqual('false', root.find('Reschedule').text)
        self.assertEqual('false', root.find('IsRegional').text)
        self.assertEqual('true', root.find('CanAutoRoute').text)
        self.assertEqual(str(subscriber_service.generate_sequence_number.return_value), root.find('PublishID').text)
        self.assertEqual('Print', root.find('Services').text)
        self.assertEqual(None, root.find('Username').text)
        self.assertEqual('false', root.find('UseLocalsOut').text)
        self.assertEqual('ap---', root.find('PscCodes').text)
        self.assertEqual('2020-04-01T11:33:12', root.find('PublishDateTime').text)

        item = root.find('ContentItem')
        self.assertEqual(None, item.find('Name').text)
        self.assertEqual('false', item.find('Cachable').text)
        self.assertEqual('false', item.find('Cachable').text)
        self.assertEqual(self.article['_id'], item.find('NewsCompID').text)

        # obvious
        self.assertEqual('Text', item.find('ContentType').text)
        self.assertEqual(self.article['headline'], item.find('Headline').text)
        self.assertEqual(self.article['creditline'], item.find('Credit').text)
        self.assertEqual(self.article['slugline'], item.find('SlugProper').text)
        self.assertEqual(self.article['source'], item.find('Source').text)
        self.assertEqual(self.article['ednote'], item.find('EditorNote').text)
        self.assertEqual(str(self.article['word_count']), item.find('WordCount').text)
        self.assertEqual(str(self.article['word_count']), item.find('BreakWordCount').text)
        self.assertEqual(str(self.article['word_count']), item.find('Length').text)
        self.assertEqual('Abstract', item.find('DirectoryText').text)
        self.assertEqual('<p>Body HTML</p>', item.find('ContentText').text)
        self.assertEqual(None, item.find('Placeline').text)
        self.assertEqual('0', item.find('WritethruValue').text)
        self.assertEqual('Foo bar,baz', item.find('Keyword').text)
        self.assertEqual('National', item.find('Category').text)
        self.assertEqual('Health,National', item.find('IndexCode').text)
        self.assertEqual(str(self.article['urgency']), item.find('RankingValue').text)

        # timestamps
        self.assertEqual('0001-01-01T00:00:00', item.find('EmbargoTime').text)
        self.assertEqual('2020-04-01T11:13:12', item.find('CreatedDateTime').text)
        self.assertEqual('2020-04-01T07:23:12-04:00', item.find('UpdatedDateTime').text)

    def test_writethru(self):
        expected_data = {
            1: '1st',
            2: '2nd',
            3: '3rd',
            4: '4th',
            5: '5th',
            10: '10th',
            100: '100th',
            101: '101st',
        }

        for val, num in expected_data.items():
            item = self.format_item({'rewrite_sequence': val})
            self.assertEqual(num, item.find('WritethruNum').text)
            self.assertEqual(str(val), item.find('WritethruValue').text)
            self.assertEqual('Writethru', item.find('WriteThruType').text)

    def test_embargo(self):
        item = self.format_item({'embargoed': self.article['firstcreated']})
        self.assertEqual('2020-04-01T11:13:12', item.find('EmbargoTime').text)

    def test_dateline(self):
        item = self.format_item({
            'dateline': {
                'source': 'AAP',
                'text': 'sample dateline',
                'located': {
                    'alt_name': '',
                    'state': 'California',
                    'city_code': 'Los Angeles',
                    'city': 'Los Angeles',
                    'dateline': 'city',
                    'country_code': 'US',
                    'country': 'USA',
                    'tz': 'America/Los_Angeles',
                    'state_code': 'CA'
                }
            },
        })
        self.assertEqual('Los Angeles', item.find('City').text)
        self.assertEqual('California', item.find('Province').text)
        self.assertEqual('USA', item.find('Country').text)
        self.assertEqual('Los Angeles;California;USA', item.find('Placeline').text)