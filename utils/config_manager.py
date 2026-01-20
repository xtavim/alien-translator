import json


class ConfigManager:
    def __init__(self, config_file_path):
        self.config_file_path = config_file_path
        self.config = self.load_config()

    def load_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {self.config_file_path}")
            return {}

    def save_config(self):
        """Save configuration to JSON file"""
        with open(self.config_file_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def get_guild_config(self, guild_id):
        """Get configuration for a specific guild"""
        return self.config.get(str(guild_id))

    def set_guild_config(
        self, guild_id, source_channel_id, target_channel_id, enabled=True
    ):
        """Set configuration for a specific guild"""
        self.config[str(guild_id)] = {
            "source": source_channel_id,
            "target": target_channel_id,
            "enabled": enabled,
        }
        self.save_config()
