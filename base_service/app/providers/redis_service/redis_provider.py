import json
from threading import Lock

import redis

from app.core.config import settings
from utils.alerting import alerter
from utils.logger import print_data

class RedisConstant:
 HOST_CACHE = "cache"
 HOST_COMMON = "common"

class RedisCacheKey:
 HOST_CACHE = "cache"
 HOST_COMMON = "common"

 # constant keys
 USER_INFO = "user_info"
 INSTITUTE_INFO = "institute_info"
 ACADEMIC_SESSION = "academic_session"
 ENUM_DATA_VALUE = "enum_data_value"

 STUDENT_PROFILE = "student_profile"
 STUDENT_CARD = "student_card"
 HOMEWORK = "student_homework"

 # Institute Enum
 INSTITUTE_PROGRAM_COURSE = "institute_program_course"
 INSTITUTE_SECTION = "institute_section"
 INSTITUTE_SUBJECT = "institute_subject"
 INSTITUTE_COURSE_FEE = "institute_course_fee"
 INSTITUTE_SECTION_LIST = "institute_section_list"
 INSTITUTE_ACADEMIC_SESSION = "institute_academic_session"
 STUDENT_INFO="student_institute_data"

class RedisCache:
 _instances = {}
 _lock = Lock()

 def __new__(cls, host_type="cache"):
 """
 host_type: 'cache' or 'common'
 """
 with cls._lock:
 if host_type not in cls._instances:
 instance = super().__new__(cls)
 cls._instances[host_type] = instance
 return cls._instances[host_type]

 def __init__(self, host_type=RedisConstant.HOST_CACHE):
 if hasattr(self, "_initialized") and self._initialized:
 return # Prevent reinitialization

 self._initialized = True
 self.host_type = host_type

 # Choose Redis config dynamically
 if host_type == RedisConstant.HOST_CACHE:
 self.client = redis.Redis(
host=settings.CACHE_REDIS_HOST,
port=settings.CACHE_REDIS_PORT,
db=settings.CACHE_REDIS_DB,
decode_responses=True,
 )
 elif host_type == RedisConstant.HOST_COMMON:
 self.client = redis.Redis(
host=settings.COMMON_REDIS_HOST,
port=settings.COMMON_REDIS_PORT,
username=settings.COMMON_REDIS_USER,
password=settings.COMMON_REDIS_PASSWORD,
decode_responses=True,
 )
 else:
 raise ValueError("Invalid host_type. Must be 'cache' or 'common'.")

 try:
 self.client.ping()
 print(f"✅ Connected to: {host_type}")
 except redis.exceptions.ConnectionError as e:
 alerter.send_alert(
message=f"{settings.PROJECT_NAME} - Redis ({host_type}) Connection Error",
extra_data={"error": str(e)},
 )
 self.client = None

 def set_data(self, key_name: str, json_data: dict | list, expire_seconds: int | None = None):
 """Store JSON data in Redis."""
 if not self.client:
 return

 try:
 json_str = json.dumps(json_data)
 self.client.set(name=key_name, value=json_str, ex=expire_seconds)
 except Exception as err:
 alerter.send_alert(
message=f"{settings.PROJECT_NAME} - Redis Set Data Error",
extra_data={"error": str(err)},
 )

 def get_data(self, key_name: str):
 """Retrieve JSON data from Redis."""
 if not self.client:
 return None

 try:
 json_str = self.client.get(key_name)
 if json_str is None:
 return None
 return json.loads(json_str)
 except Exception as err:
 alerter.send_alert(
message=f"{settings.PROJECT_NAME} - Redis Get Data Error",
extra_data={"error": str(err)},
 )
 return None

 def delete_data(self, key_name: str):
 """Delete a key from Redis."""
 if not self.client:
 return

 try:
 result = self.client.delete(key_name)
 if result == 1:
 print_data(f"🗑️ Key '{key_name}' deleted successfully.")
 except Exception as err:
 alerter.send_alert(
message=f"{settings.PROJECT_NAME} - Redis Delete Data Error",
extra_data={"error": str(err)},
 )