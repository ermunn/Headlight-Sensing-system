import os
import unittest
from unittest.mock import MagicMock, patch

import app


class CaptureTest(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()
        self.image = b'\xff\xd8test\xff\xd9'
        self.headers = {'X-Upload-Token': 'test', 'X-LDR-Value': '2.1'}
        self.env = patch.dict(os.environ, {'PHOTO_UPLOAD_TOKEN': 'test', 'PLATE_RECOGNIZER_TOKEN': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_capture_links_photo_to_new_measurement(self):
        for plate in ('Танигдаагүй', '1234ABC'):
            with self.subTest(plate=plate):
                connection = MagicMock()
                cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
                cursor.fetchone.side_effect = [(42,), (7, 42, '2026-10-21')]
                blob = MagicMock(url='https://example.com/photo', pathname='photo.jpg')
                with patch.object(app, 'recognize_plate', return_value=(plate, 'test')), \
                        patch.object(app, 'get_db_connection', return_value=connection), \
                        patch('vercel.blob.sync.put_blob', return_value=blob):
                    response = self.client.post('/api/captures', data=self.image,
                                                content_type='image/jpeg', headers=self.headers)
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json['measurement_id'], 42)
                self.assertEqual(response.json['unit'], 'V')
                self.assertEqual(cursor.execute.call_args_list[0].args[1],
                                 (plate, 2.1, app.DEFAULT_LIMIT_VALUE, 'Fail'))
                self.assertEqual(cursor.execute.call_args_list[1].args[1][0], 42)

    def test_invalid_voltage_never_writes(self):
        with patch.object(app, 'get_db_connection') as database:
            for voltage in ('', 'nan', 'inf', '-1', '3.4', 'bad'):
                headers = dict(self.headers, **{'X-LDR-Value': voltage})
                response = self.client.post('/api/captures', data=self.image,
                                            content_type='image/jpeg', headers=headers)
                self.assertEqual(response.status_code, 400)
            database.assert_not_called()

    def test_unauthorized_and_invalid_jpeg(self):
        response = self.client.post('/api/captures', data=self.image, content_type='image/jpeg')
        self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/captures', data=b'bad!',
                                    content_type='image/jpeg', headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_ocr_without_configuration(self):
        self.assertEqual(app.recognize_plate(self.image), ('Танигдаагүй', 'not_configured'))

    def test_ocr_results_and_failure(self):
        with patch.dict(os.environ, {'PLATE_RECOGNIZER_TOKEN': 'test'}):
            for results, expected in [([], 'Танигдаагүй'),
                                      ([{'plate': '1234abc', 'score': 0.95}], '1234ABC'),
                                      ([{'plate': 'bad', 'score': 0.2}], 'Танигдаагүй')]:
                with patch.object(app, 'urlopen') as request:
                    request.return_value.__enter__.return_value.read.return_value = app.json.dumps({'results': results})
                    self.assertEqual(app.recognize_plate(self.image)[0], expected)
            with patch.object(app, 'urlopen', side_effect=TimeoutError):
                self.assertEqual(app.recognize_plate(self.image)[1], 'unavailable')


if __name__ == '__main__':
    unittest.main()
