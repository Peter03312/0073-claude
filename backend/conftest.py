"""保证 tests 能从仓库的 backend/ 目录直接导入 app 包。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
