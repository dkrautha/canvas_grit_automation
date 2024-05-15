from typing import Self
import subprocess
import pymsteams
import re
from pydantic import BaseModel

class FailSend(BaseModel):
  seconds=10
  netunreach = "Destination Net Unreachable"
  myTeamsMessage = pymsteams.connectorcard("<Microsoft Webhook URL>")
  pingstr = str((subprocess.run(['ping','192.168.195.89/'], capture_output=True, timeout=seconds)))
  def TestGrit(ip:str, seconds:int, netunreach:str, pingstr:str):
    if  re.search(netunreach, pingstr) == None :
      


__all__ = ["FailSend"]
