"""GNU Make fixture test only, not Soong/lunch or an Android build."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

OVERLAY = Path(__file__).resolve().parents[2] / 'overlay/vendor/doxaiz'


class CuttlefishProductTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('make'), 'GNU Make needed')
    def test_registration_and_upstream_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(OVERLAY, root / 'vendor/doxaiz')
            upstream = root / 'device/google/cuttlefish/vsoc_x86_64_only/phone/aosp_cf.mk'
            upstream.parent.mkdir(parents=True)
            upstream.write_text('''PRODUCT_NAME := stock
PRODUCT_DEVICE := vsoc_x86_64_only
PRODUCT_IGNORE_ALL_ANDROIDMK := true
USE_SOONG_DEFINED_SYSTEM_IMAGE := true
PRODUCT_SOONG_ONLY := true
''')
            (root / 'test.mk').write_text('''LOCAL_DIR := vendor/doxaiz
include vendor/doxaiz/AndroidProducts.mk
registration := $(filter doxaiz_cf_x86_64_phone:%,$(PRODUCT_MAKEFILES))
product_path := $(word 2,$(subst :, ,$(registration)))
inherit-product = $(eval include $(1))
include $(product_path)
all:
\t@echo $(PRODUCT_NAME) $(PRODUCT_DEVICE) $(PRODUCT_IGNORE_ALL_ANDROIDMK) $(USE_SOONG_DEFINED_SYSTEM_IMAGE) $(PRODUCT_SOONG_ONLY)
\t@echo $(PRODUCT_PACKAGES)
\t@echo $(PRODUCT_PROPERTY_OVERRIDES)
\t@echo $(COMMON_LUNCH_CHOICES)
''')
            result = subprocess.run(['make', '-s', '-f', 'test.mk'], cwd=root,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            lines = result.stdout.splitlines()
            self.assertEqual(lines[0], 'doxaiz_cf_x86_64_phone vsoc_x86_64_only false false false')
            self.assertIn('DoxaizLauncher', lines[1].split())
            self.assertIn('ro.config.low_ram=true', lines[2].split())
            self.assertIn('ro.doxaiz.version=0.1.0', lines[2].split())
            self.assertIn('doxaiz_cf_x86_64_phone-trunk_staging-userdebug', lines[3])


if __name__ == '__main__':
    unittest.main()
