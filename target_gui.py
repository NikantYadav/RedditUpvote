import customtkinter as ctk
import asyncio
import logging
import threading
from datetime import datetime
from target import orchestrate_batches

# Setup standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Reddit-inspired color scheme
COLORS = {
    "primary": "#1A1A1B",       # Reddit dark bg
    "secondary": "#272729",     # Slightly lighter bg
    "accent": "#FF4500",        # Reddit orange
    "success": "#46D160",       # Green
    "danger": "#FF585B",        # Red
    "text": "#D7DADC",          # Reddit light text
    "border": "#343536"         # Reddit border color
}

class UpvoteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Reddit Upvote Orchestrator")
        self.geometry("800x600")
        
        # Configure appearance mode and color theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("dark-blue")  # Use built-in dark theme as base
        
        # Override theme colors
        self.configure(fg_color=COLORS["primary"])
        
        # Font setup
        self.bold_font = ctk.CTkFont(family="Arial", size=14, weight="bold")
        self.title_font = ctk.CTkFont(family="Arial", size=24, weight="bold")
        self.mono_font = ctk.CTkFont(family="Consolas", size=12)

        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(pady=40, padx=40, fill="both", expand=True)

        # Header
        ctk.CTkLabel(
            self.main_frame,
            text="REDDIT UPVOTE MANAGER",
            font=self.title_font,
            text_color=COLORS["accent"]
        ).pack(pady=(0, 20))

        # Create instance button
        self.create_instance_button = ctk.CTkButton(
            self.main_frame,
            text="➕ NEW INSTANCE",
            command=self.create_instance_ui,
            width=300,
            height=60,
            font=self.bold_font,
            fg_color=COLORS["accent"],
            hover_color="#FF5714",
            corner_radius=8,
            border_color=COLORS["border"],
            border_width=1
        )
        self.create_instance_button.pack(pady=20)

    def create_instance_ui(self):
        instance_window = ctk.CTkToplevel(self)
        instance_window.title("Upvote Instance")
        instance_window.geometry("800x800")
        instance_window.configure(fg_color=COLORS["primary"])

        # Main container
        container = ctk.CTkFrame(instance_window, fg_color="transparent")
        container.pack(pady=30, padx=40, fill="both", expand=True)

        # Input Section
        input_frame = ctk.CTkFrame(container, 
                                  fg_color=COLORS["secondary"], 
                                  corner_radius=8,
                                  border_color=COLORS["border"],
                                  border_width=1)
        input_frame.pack(fill="x", pady=(0, 20))

        # Form elements
        form_elements = [
            ("Reddit Post URL", "https://reddit.com/r/.../post_id"),
            ("Votes per Minute", "e.g., 2"),
            ("Total Votes", "e.g., 10"),
            ("Account IDs", "e.g., 1-5 or 1,2,3")
        ]

        for idx, (label, placeholder) in enumerate(form_elements):
            ctk.CTkLabel(
                input_frame,
                text=label + ":",
                font=self.bold_font,
                text_color=COLORS["text"]
            ).grid(row=idx, column=0, padx=20, pady=10, sticky="w")
            
            entry = ctk.CTkEntry(
                input_frame,
                width=500,
                placeholder_text=placeholder,
                font=self.mono_font,
                corner_radius=6,
                border_color=COLORS["border"],
                fg_color=COLORS["primary"],
                text_color=COLORS["text"]
            )
            entry.grid(row=idx, column=1, padx=20, pady=10)

        # Start button
        start_button = ctk.CTkButton(
            container,
            text="🔼 START UPVOTING",
            command=lambda: self.start_upvoting_threaded(
                *[input_frame.children[f"!ctkentry{i+1}"] for i in range(4)],
                instance_window
            ),
            width=300,
            height=50,
            font=self.bold_font,
            fg_color=COLORS["accent"],
            hover_color="#FF5714",
            corner_radius=8,
            border_color=COLORS["border"],
            border_width=1
        )
        start_button.pack(pady=20)

        # Log box
        log_box = ctk.CTkTextbox(
            container,
            width=700,
            height=300,
            fg_color=COLORS["secondary"],
            text_color=COLORS["text"],
            font=self.mono_font,
            corner_radius=8,
            border_color=COLORS["border"],
            border_width=1
        )
        log_box.pack(pady=(10, 0))
        instance_window.log_box = log_box

    def parse_account_ids(self, input_str: str):
        """Parse ranges like '1-5' or comma-separated '1,2,3'"""
        try:
            if "-" in input_str:
                start, end = map(int, input_str.split("-"))
                return list(range(start, end + 1))
            return list(map(int, input_str.split(",")))
        except ValueError:
            return None

    def start_upvoting_threaded(self, post_url_entry, votes_per_min_entry, total_votes_entry, account_ids_entry, instance_window):
        """Starts a new thread for this upvoting task"""
        thread = threading.Thread(
            target=self.run_async_upvote,
            args=(post_url_entry, votes_per_min_entry, total_votes_entry, account_ids_entry, instance_window),
            daemon=True
        )
        thread.start()

    def run_async_upvote(self, post_url_entry, votes_per_min_entry, total_votes_entry, account_ids_entry, instance_window):
        """Runs the asyncio event loop in this thread"""
        asyncio.run(self._start_upvoting(post_url_entry, votes_per_min_entry, total_votes_entry, account_ids_entry, instance_window))

    async def _start_upvoting(self, post_url_entry, votes_per_min_entry, total_votes_entry, account_ids_entry, instance_window):
        """Async logic to run the upvoting"""
        post_url = post_url_entry.get().strip()
        account_ids_input = account_ids_entry.get().strip()

        try:
            votes_per_min = int(votes_per_min_entry.get())
            total_votes = int(total_votes_entry.get())
        except ValueError:
            self.log("❌ Invalid input: Votes must be integers.", instance_window, COLORS["danger"])
            return

        account_ids = self.parse_account_ids(account_ids_input)
        if account_ids is None:
            self.log("❌ Invalid account ID format. Use '1-5' or '1,2,3'", instance_window, COLORS["danger"])
            return

        self.log(f"🚀 Starting upvote task for: {post_url}", instance_window)
        self.log(f"⚙️  Votes/min: {votes_per_min}, Total: {total_votes}", instance_window)
        self.log(f"👥 Using Accounts: {account_ids}", instance_window)

        try:
            await orchestrate_batches(
                post_url=post_url,
                account_ids=account_ids,
                votes_per_min=votes_per_min,
                total_votes=total_votes
            )
            self.log("✅ Upvoting completed.", instance_window, COLORS["success"])
        except Exception as e:
            self.log(f"❌ Error: {str(e)}", instance_window, COLORS["danger"])

    def log(self, message: str, window, color=COLORS["text"]):
        """Insert styled message into the log box"""
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        window.log_box.tag_config(color, foreground=color)
        window.log_box.insert("end", f"{timestamp} ", ("bold", color))
        window.log_box.insert("end", f"{message}\n", color)
        window.log_box.see("end")

if __name__ == "__main__":
    app = UpvoteApp()
    app.mainloop()