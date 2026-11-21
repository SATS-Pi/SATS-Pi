import os
import tempfile

# Réglages de test posés avant tout import de l'application (ordre des fichiers indifférent).
os.environ.update(
    LIGHTNING_MODE="mock",
    PAYOUT_MODE="mock",
    FX_MODE="fixed",
    FIXED_BTC_XOF="60000000",
    POLL_INTERVAL_S="0.1",
    MOCK_PAYOUT_DELAY_S="0.05",
    ADMIN_TOKEN="test-token",
    DB_PATH=os.path.join(tempfile.mkdtemp(), "test.db"),
)
