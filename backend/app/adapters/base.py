from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseNotificationAdapter(ABC):
    @abstractmethod
    def send(self, notification_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches notification to destination channel.
        Returns result dict containing status, channel, and details.
        """
        pass
