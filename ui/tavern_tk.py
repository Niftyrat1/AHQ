"""
Tavern screen using tkinter instead of pygame.
"""

import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import List, Optional, Callable
from hero import Hero, HeroManager, roll_hero_race, roll_hero_stats, roll_starting_gold


class TavernScreenTk:
    """Tavern / party management screen using tkinter."""
    
    def __init__(self, root: tk.Tk, on_begin_quest: Optional[Callable] = None):
        self.root = root
        self.on_begin_quest = on_begin_quest
        
        self.hero_manager = HeroManager()
        self.heroes: List[Hero] = []
        self.party: List[Hero] = []
        self.selected_hero: Optional[Hero] = None
        
        self.creation_mode = False
        self.new_hero_data = {}
        
        self._setup_ui()
        self.refresh_hero_list()
    
    def _setup_ui(self):
        """Set up the UI layout."""
        self.root.title("Advanced HeroQuest - The Tavern")
        self.root.geometry("900x600")
        
        # Main frames
        self.left_frame = tk.Frame(self.root, width=400, bg="#2a2a35")
        self.left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        self.right_frame = tk.Frame(self.root, width=400, bg="#2a2a35")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Hero roster list
        tk.Label(self.left_frame, text="Hero Roster", font=("Arial", 14, "bold"), bg="#2a2a35", fg="#ddd").pack(anchor=tk.W)
        
        self.hero_listbox = tk.Listbox(self.left_frame, width=50, height=15, font=("Courier", 10),
                                       selectmode=tk.MULTIPLE)
        self.hero_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.hero_listbox.bind('<<ListboxSelect>>', self._on_hero_select)
        
        # Hero roster buttons
        btn_frame = tk.Frame(self.left_frame, bg="#2a2a35")
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="Create Hero", command=self._start_hero_creation,
                 bg="#4a7", fg="white", width=12).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text="Delete Hero", command=self._delete_hero,
                 bg="#a44", fg="white", width=12).pack(side=tk.LEFT, padx=2)
        
        # Party management
        tk.Label(self.left_frame, text="Party (max 4)", font=("Arial", 12, "bold"), bg="#2a2a35", fg="#ddd").pack(anchor=tk.W, pady=(10, 0))
        
        self.party_listbox = tk.Listbox(self.left_frame, width=50, height=4, font=("Courier", 10))
        self.party_listbox.pack(fill=tk.X, pady=5)
        
        party_btn_frame = tk.Frame(self.left_frame, bg="#2a2a35")
        party_btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(party_btn_frame, text="Add to Party", command=self._add_to_party,
                 width=15).pack(side=tk.LEFT, padx=2)
        tk.Button(party_btn_frame, text="Remove from Party", command=self._remove_from_party,
                 width=15).pack(side=tk.LEFT, padx=2)
        
        # Begin Quest button
        self.begin_btn = tk.Button(self.left_frame, text="BEGIN QUEST",
                                  command=self._begin_quest,
                                  bg="#44a", fg="white", font=("Arial", 12, "bold"),
                                  height=2, state=tk.DISABLED)
        self.begin_btn.pack(fill=tk.X, pady=20)
        
        # Hero detail panel (right side)
        tk.Label(self.right_frame, text="Hero Details", font=("Arial", 14, "bold"), bg="#2a2a35", fg="#ddd").pack(anchor=tk.W)
        
        self.detail_text = tk.Text(self.right_frame, width=40, height=20, font=("Courier", 11),
                                   bg="#222", fg="#ddd", insertwidth=0,
                                   takefocus=0, selectbackground="#222", selectforeground="#ddd")
        self.detail_text.pack(fill=tk.BOTH, expand=True, pady=5)
        self.detail_text.config(state=tk.DISABLED)
        
        self._update_detail_panel()
    
    def refresh_hero_list(self):
        """Refresh the list of heroes."""
        self.heroes = self.hero_manager.get_all_heroes()
        
        self.hero_listbox.delete(0, tk.END)
        for hero in self.heroes:
            display = f"{hero.name:15} | {hero.race:6} {hero.class_type:7} | WS:{hero.ws:2} | W:{hero.current_wounds:2}/{hero.max_wounds} | F:{hero.current_fate}"
            self.hero_listbox.insert(tk.END, display)
    
    def _on_hero_select(self, event):
        """Handle hero selection."""
        selection = self.hero_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.heroes):
                self.selected_hero = self.heroes[index]
                self._update_detail_panel()
    
    def _update_detail_panel(self):
        """Update the hero detail display."""
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)
        
        if self.selected_hero:
            h = self.selected_hero
            lines = [
                f"Name:  {h.name}",
                f"Race:  {h.race}",
                f"Class: {h.class_type}",
                "",
                "Statistics:",
                f"  Weapon Skill:    {h.ws:2}",
                f"  Ballistic Skill: {h.bs:2}",
                f"  Strength:        {h.strength:2}",
                f"  Toughness:       {h.toughness:2}",
                f"  Speed:           {h.speed:2}",
                f"  Bravery:         {h.bravery:2}",
                f"  Intelligence:    {h.intelligence:2}",
                "",
                f"Wounds: {h.current_wounds}/{h.max_wounds}",
                f"Fate:   {h.current_fate}/{h.max_fate}",
                f"Gold:   {h.gold}",
                "",
                "Equipment:",
            ]
            for item in h.equipment:
                lines.append(f"  - {item['name']}")
            
            self.detail_text.insert(tk.END, "\n".join(lines))
        else:
            self.detail_text.insert(tk.END, "\n  Select a hero to\n  view their details.")
        
        self.detail_text.config(state=tk.DISABLED)
    
    def _add_to_party(self):
        """Add selected heroes to party."""
        selection = self.hero_listbox.curselection()
        added = 0
        for index in selection:
            if len(self.party) >= 4:
                break
            hero = self.heroes[index]
            if hero not in self.party:
                self.party.append(hero)
                added += 1
        if added > 0:
            self._update_party_list()
    
    def _remove_from_party(self):
        """Remove selected hero from party."""
        selection = self.party_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.party):
                self.party.pop(index)
                self._update_party_list()
    
    def _update_party_list(self):
        """Update party listbox."""
        self.party_listbox.delete(0, tk.END)
        for hero in self.party:
            display = f"{hero.name} | {hero.race} {hero.class_type} | W:{hero.current_wounds}/{hero.max_wounds}"
            self.party_listbox.insert(tk.END, display)
        
        # Enable/disable begin quest button
        if self.party:
            self.begin_btn.config(state=tk.NORMAL)
        else:
            self.begin_btn.config(state=tk.DISABLED)
    
    def _delete_hero(self):
        """Delete selected hero."""
        if self.selected_hero:
            if messagebox.askyesno("Confirm", f"Delete {self.selected_hero.name}?"):
                self.hero_manager.delete_hero(self.selected_hero.id)
                self.selected_hero = None
                self.refresh_hero_list()
                self._update_detail_panel()
    
    def _begin_quest(self):
        """Start the dungeon quest."""
        if self.party and self.on_begin_quest:
            self.on_begin_quest(self.party)
    
    def _start_hero_creation(self):
        """Open hero creation dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Hero")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Step 1: Race
        tk.Label(dialog, text="Step 1: Roll for Race", font=("Arial", 12, "bold")).pack(pady=5)
        
        race_var = tk.StringVar(value="")
        race_label = tk.Label(dialog, text="Race: Not rolled", font=("Arial", 11))
        race_label.pack()
        
        def roll_race():
            race = roll_hero_race()
            race_var.set(race)
            race_label.config(text=f"Race: {race}")
            roll_race_btn.config(state=tk.DISABLED)
            class_frame.pack(pady=10)
        
        roll_race_btn = tk.Button(dialog, text="Roll Race (D12)", command=roll_race)
        roll_race_btn.pack(pady=5)
        
        # Step 2: Class
        class_frame = tk.Frame(dialog)
        tk.Label(class_frame, text="Step 2: Choose Class", font=("Arial", 12, "bold")).pack()
        
        class_var = tk.StringVar(value="Warrior")
        tk.Radiobutton(class_frame, text="Warrior", variable=class_var, value="Warrior").pack()
        tk.Radiobutton(class_frame, text="Wizard (no armour, dagger only)",
                      variable=class_var, value="Wizard").pack()
        
        def show_stats():
            class_frame.pack_forget()
            stats_frame.pack(pady=10)
        
        tk.Button(class_frame, text="Continue to Stats", command=show_stats,
                 bg="#44a", fg="white").pack(pady=10)
        
        # Step 3: Stats
        stats_frame = tk.Frame(dialog)
        tk.Label(stats_frame, text="Step 3: Stats", font=("Arial", 12, "bold")).pack()
        
        stats_text = tk.Text(stats_frame, width=30, height=8, font=("Courier", 10))
        stats_text.pack()
        stats_text.config(state=tk.DISABLED)
        
        def roll_stats():
            stats = roll_hero_stats(race_var.get())
            stats_text.config(state=tk.NORMAL)
            stats_text.delete(1.0, tk.END)
            for key, val in stats.items():
                stats_text.insert(tk.END, f"{key}: {val}\n")
            stats_text.config(state=tk.DISABLED)
            roll_stats_btn.config(state=tk.DISABLED)
            stats_continue_btn.pack(pady=5)
        
        def show_gold():
            stats_frame.pack_forget()
            gold_frame.pack(pady=10)
        
        stats_continue_btn = tk.Button(stats_frame, text="Continue to Gold",
                                      command=show_gold, bg="#44a", fg="white")
        
        roll_stats_btn = tk.Button(stats_frame, text="Roll Stats", command=roll_stats)
        roll_stats_btn.pack(pady=5)
        
        # Step 4: Gold
        gold_frame = tk.Frame(dialog)
        tk.Label(gold_frame, text="Step 4: Starting Gold", font=("Arial", 12, "bold")).pack()
        
        gold_var = tk.IntVar(value=0)
        gold_label = tk.Label(gold_frame, text="Gold: 0 gc", font=("Arial", 11))
        gold_label.pack()
        
        def roll_gold():
            gold = roll_starting_gold()
            gold_var.set(gold)
            gold_label.config(text=f"Gold: {gold} gc")
            roll_gold_btn.config(state=tk.DISABLED)
            gold_continue_btn.pack(pady=5)
        
        def show_name():
            gold_frame.pack_forget()
            name_frame.pack(pady=10)
        
        gold_continue_btn = tk.Button(gold_frame, text="Continue to Name",
                                     command=show_name, bg="#44a", fg="white")
        
        roll_gold_btn = tk.Button(gold_frame, text="Roll Gold (D4+4 x 10)", command=roll_gold)
        roll_gold_btn.pack(pady=5)
        
        # Step 5: Name
        name_frame = tk.Frame(dialog)
        tk.Label(name_frame, text="Step 5: Name", font=("Arial", 12, "bold")).pack()
        
        name_entry = tk.Entry(name_frame, width=20)
        name_entry.pack(pady=5)
        
        # Name lists for randomizer
        first_names = ["Aldric", "Borin", "Cedric", "Doran", "Eldar", "Fenris", "Gareth", "Halric",
                      "Ivan", "Jorah", "Kael", "Loric", "Magnus", "Norrin", "Orik", "Perrin",
                      "Quint", "Ragnar", "Soren", "Thorin", "Ulric", "Varian", "Wulfric", "Xander",
                      "Yorick", "Zane", "Aeliana", "Brianna", "Cassandra", "Diana", "Elara", "Fiona"]
        last_names = ["Ironheart", "Stormbreaker", "Doomsayer", "Swiftblade", "Stonefist",
                     "Shadowbane", "Fireborn", "Frostwind", "Thunderaxe", "Dragonbane",
                     "Steelguard", "Ravenwood", "Blackwood", "Silverhand", "Goldmane",
                     "Brightsword", "Darkhollow", "Wolfheart", "Eagleeye", "Bearclaw"]
        
        def random_name():
            import random
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            name_entry.delete(0, tk.END)
            name_entry.insert(0, name)
        
        tk.Button(name_frame, text="Random Name", command=random_name,
                 bg="#66a", fg="white").pack(pady=2)
        
        def finish():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Please enter a name")
                return
            
            # Get stats from the display
            stats_str = stats_text.get(1.0, tk.END)
            stats = {}
            for line in stats_str.strip().split("\n"):
                if ":" in line:
                    key, val = line.split(":")
                    stats[key.strip()] = int(val.strip())
            
            # Basic equipment
            equipment = [{"name": "Dagger", "type": "weapon", "equipped": True}]
            
            # Create hero
            hero = self.hero_manager.create_hero(
                name=name,
                race=race_var.get(),
                class_type=class_var.get(),
                stats=stats,
                gold=gold_var.get(),
                equipment=equipment
            )
            
            self.selected_hero = hero
            dialog.destroy()
            self.refresh_hero_list()
            self._update_detail_panel()
        
        btn_frame_final = tk.Frame(name_frame)
        btn_frame_final.pack(pady=10)
        
        tk.Button(btn_frame_final, text="Create Hero", command=finish,
                 bg="#4a7", fg="white", width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_final, text="Cancel", command=dialog.destroy,
                 bg="#a44", fg="white", width=10).pack(side=tk.LEFT, padx=5)
        
        # Class frame shows initially (after race roll)
        # Stats/gold/name frames will be shown by their "Continue" buttons
