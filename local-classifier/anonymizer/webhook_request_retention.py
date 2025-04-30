import os
from collections import deque

class RequestRetentionList:
    def __init__(self):
        self.retention_limit = int(os.getenv('EMAIL_ID_RETENTION_LIMIT', '100'))
        self.email_list = deque(maxlen=self.retention_limit)

    def add_email(self, email_id: str) -> bool:
        if email_id in self.email_list:
            print(self.email_list)
            return False
        else:
            self.email_list.append(email_id)
            print(self.email_list)
            return True