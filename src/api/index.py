import os
import sys


current_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, current_dir)


from main import app

handler = app
