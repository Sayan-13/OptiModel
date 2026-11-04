import json
import unittest
from unittest.mock import patch

from backend.app.nlp_generator import ProcessNLPGenerator


XML = '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL"><process id="p"/></definitions>'


class ProviderTests(unittest.TestCase):
    def test_missing_key_does_not_use_heuristic_fallback(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'MAKEREND_API_KEY'):
                ProcessNLPGenerator.generate_bpmn_xml('Review request')

    def test_model_response_is_validated(self):
        with patch.dict('os.environ', {'MAKEREND_API_KEY': 'test'}, clear=True):
            with patch.object(ProcessNLPGenerator, '_generate_via_openai', return_value=XML):
                self.assertEqual(ProcessNLPGenerator.generate_bpmn_xml('Review request'), XML)
            with patch.object(ProcessNLPGenerator, '_generate_via_openai', return_value='<invalid>'):
                with self.assertRaisesRegex(RuntimeError, 'invalid BPMN XML'):
                    ProcessNLPGenerator.generate_bpmn_xml('Review request')

    def test_configured_endpoint_and_model(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return json.dumps({'choices': [{'message': {'content': XML}}]}).encode()

        env = {'MAKEREND_API_KEY': 'test', 'MAKEREND_MODEL': 'custom', 'MAKEREND_BASE_URL': 'https://example.test/v1/'}
        with patch.dict('os.environ', env, clear=True), patch('urllib.request.urlopen', return_value=Response()) as call:
            ProcessNLPGenerator.generate_bpmn_xml('Review request')
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, 'https://example.test/v1/chat/completions')
            self.assertEqual(json.loads(request.data)['model'], 'custom')


if __name__ == '__main__':
    unittest.main()
