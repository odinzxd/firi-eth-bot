from dotenv import load_dotenv
import os

load_dotenv()

print("Firi ETH-bot starter...")
print("Marked:", os.getenv("MARKET"))
print("Dry run:", os.getenv("DRY_RUN"))
print("Maks handel:", os.getenv("MAX_TRADE_NOK"), "NOK")