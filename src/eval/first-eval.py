import unittest
import os
import sys

# Setup modular import paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, 'src', 'core'))
sys.path.insert(0, os.path.join(BASE_DIR, 'src', 'tools'))
sys.path.insert(0, os.path.join(BASE_DIR, 'src', 'agents'))

from core.schema import SMMEProfile
from core.crypto import CredentialEncryptor, POPIADataMasker
from agents.gemini_client import GeminiClient
from agents.orchestrator import ModularADKOrchestrator

class TestModularGeminiSystem(unittest.TestCase):

    def setUp(self):
        self.profile = SMMEProfile()
        self.orchestrator = ModularADKOrchestrator()

    def test_credential_encryption(self):
        encryptor = CredentialEncryptor()
        cred = encryptor.encrypt("SARS_eFiling", "MySecretPass123")
        decrypted = encryptor.decrypt(cred)
        self.assertEqual(decrypted, "MySecretPass123")

    def test_popia_masking(self):
        masked_id = POPIADataMasker.mask_id_number("8901015000087")
        self.assertEqual(masked_id, "890101*****87")

        sanitized = POPIADataMasker.sanitize_prompt_text("ID is 8901015000087 and phone is 0821234567")
        self.assertIn("[REDACTED_SA_ID]", sanitized)
        self.assertIn("[REDACTED_PHONE]", sanitized)

    def test_gemini_client_parse(self):
        client = GeminiClient()
        res = client.parse_gemini_response("Refresh my tax compliance pin", "Profile summary")
        self.assertEqual(res["tool_name"], "refresh_sars_tcs")

    def test_orchestrator_tax_tcs_refresh(self):
        self.profile.compliance.tcs_pin_expiry_days = 2
        res = self.orchestrator.process_user_query("Please refresh my SARS tax compliance pin", self.profile)
        self.assertEqual(self.profile.compliance.tcs_pin_expiry_days, 365)
        self.assertTrue(self.profile.compliance.tax_compliant)
        self.assertIn("SARS Tax Compliance Status", res["response_text"])

    def test_orchestrator_tender_pack(self):
        res = self.orchestrator.process_user_query("Apply for catering tender in Mangaung", self.profile)
        self.assertIn("MBD 4", res["response_text"])
        self.assertIn("MBD 6.1", res["response_text"])

if __name__ == "__main__":
    unittest.main()