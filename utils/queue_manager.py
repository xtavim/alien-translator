import asyncio
import json
import threading
import time
from queue import Queue, Empty
import discord
from .translator import translate_message_with_links

class TranslationQueueManager:
    """Manages a queue of translation jobs to ensure messages are processed in order.

    Key feature: Sequential processing guarantees message order regardless of API response times.
    """

    def __init__(self, bot, config_file="config.json"):
        self.bot = bot
        self.translation_queue = Queue()
        self.worker_running = False
        self.worker_thread = None
        self.config_file = config_file
        self.rate_limit_delay = self._load_config().get("rateLimitDelay", 1.0)  # Default 1.0s delay

    class MessageJob:
        """Represents a translation job for a message"""
        def __init__(self, message, guild_cfg):
            self.message = message
            self.guild_cfg = guild_cfg
            self.timestamp = time.time()

    def add_message(self, message, guild_cfg):
        """Add a message to the translation queue"""
        job = self.MessageJob(message, guild_cfg)
        self.translation_queue.put(job)

        # Start worker thread if not already running
        if not self.worker_running or (self.worker_thread and not self.worker_thread.is_alive()):
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()

        return job

    def _process_queue(self):
        """Worker thread function to process messages from the queue in order.

        CRITICAL: This ensures message order by processing messages sequentially.
        Each message is fully processed (translation + Discord post) before
        the next message is started, regardless of API response time.
        """
        self.worker_running = True

        print("Translation queue worker started")

        while self.worker_running:
            try:
                # Get a job from the queue with timeout
                # FIFO queue ensures messages are processed in order of receipt
                job = self.translation_queue.get(timeout=1.0)

                # Process the translation
                # NOTE: This blocks until complete, ensuring order is maintained
                print(f"Processing message from {job.message.author.display_name}: '{job.message.content[:50]}...'")

                # Translate the message (handling links properly)
                translated = translate_message_with_links(job.message.content, target="en")

                # Skip if no translation is needed (English message, link-only, or other reason)
                if translated is None:
                    print(f"Skipping message - no translation needed")
                    self.translation_queue.task_done()
                    continue

                print(f"Translated message: '{translated[:50]}...'")

                # Create an embed with user avatar, name, timestamp and translated message
                embed = discord.Embed(
                    description=translated,
                    color=job.message.author.color,
                    timestamp=job.message.created_at
                )
                embed.set_author(
                    name=job.message.author.display_name,
                    icon_url=job.message.author.display_avatar.url if job.message.author.display_avatar else None
                )

                # Send to target channel
                target_channel = self.bot.get_channel(job.guild_cfg["target"])
                if target_channel:
                    # Use asyncio to send message from this thread to Discord
                    asyncio.run_coroutine_threadsafe(
                        target_channel.send(embed=embed),
                        self.bot.loop
                    )
                else:
                    print(f"Could not find target channel with ID: {job.guild_cfg['target']}")

                # Mark job as done
                self.translation_queue.task_done()

                # Apply rate limiting between API calls
                # This delay happens AFTER each message is completely processed
                # It does not affect the ordering guarantee
                time.sleep(self.rate_limit_delay)

            except Empty:
                # No items in queue, continue loop
                continue
            except Exception as e:
                print(f"Error in translation queue worker: {e}")
                # Mark job as done even if there was an error
                try:
                    self.translation_queue.task_done()
                except:
                    pass

        print("Translation queue worker stopped")

    def start(self):
        """Start the queue worker if not already running"""
        if not self.worker_running or (self.worker_thread and not self.worker_thread.is_alive()):
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()

    def stop(self):
        """Stop the queue worker"""
        self.worker_running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)

    def _load_config(self):
        """Load queue settings from config file"""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                return config.get("queueSettings", {})
        except FileNotFoundError:
            print(f"Config file {self.config_file} not found, using defaults")
            return {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {self.config_file}, using defaults")
            return {}

    def _save_config(self):
        """Save queue settings to config file"""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
        except FileNotFoundError:
            config = {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from {self.config_file}, creating new file")
            config = {}

        # Update queue settings
        config["queueSettings"] = {
            "rateLimitDelay": self.rate_limit_delay
        }

        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def set_rate_limit(self, delay):
        """Set the rate limit delay and save to config"""
        self.rate_limit_delay = delay
        self._save_config()

    def clear_queue(self):
        """Clear all pending jobs from the queue"""
        # Empty the queue without processing
        while not self.translation_queue.empty():
            try:
                self.translation_queue.get_nowait()
                self.translation_queue.task_done()
            except Empty:
                break
        print(f"Cleared {self.translation_queue.qsize()} items from translation queue")

    def pause(self):
        """Pause processing of the queue"""
        self.worker_running = False
        print("Translation queue paused")

    def resume(self):
        """Resume processing of the queue"""
        if not self.worker_running or (self.worker_thread and not self.worker_thread.is_alive()):
            self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self.worker_thread.start()
        print("Translation queue resumed")

    def get_queue_size(self):
        """Get the current size of the queue"""
        return self.translation_queue.qsize()

    def is_worker_running(self):
        """Check if the worker thread is currently running"""
        return self.worker_running and (self.worker_thread and self.worker_thread.is_alive())

    def get_queue_order(self, max_items=10):
        """Get a snapshot of the current queue order for debugging
        Returns a list of message author names and content previews
        """
        queue_items = []

        # Create a copy of the queue to inspect without modifying it
        # We need to be careful here as we're accessing a thread-safe queue
        with self.translation_queue.mutex:
            # Get a snapshot of the queue
            queue_snapshot = list(self.translation_queue.queue)

            # Extract limited
