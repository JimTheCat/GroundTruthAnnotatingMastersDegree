"""
Data Manager for Text Annotations
Handles loading/saving annotations and static data
"""

import streamlit as st
import pandas as pd
import json
import os
from typing import Dict, List
from config import TEXTS_FILE, CATEGORIES_FILE


# ============================================================================
# CACHED DATA LOADERS
# ============================================================================

@st.cache_data
def load_texts() -> pd.DataFrame:
    """
    Load texts from file.

    Format: Each line is "ID TEXT_CONTENT"
    Returns: DataFrame with columns ['id', 'tekst']
    """
    rows = []
    with open(TEXTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(maxsplit=1)
                rows.append({
                    "id": parts[0],
                    "tekst": parts[1] if len(parts) == 2 else ""
                })
    return pd.DataFrame(rows)


@st.cache_data
def load_categories() -> List[str]:
    """
    Load categories from JSON file.

    Returns: Sorted list of category names
    """
    with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
        return sorted(json.load(f))


# ============================================================================
# ANNOTATIONS MANAGER
# ============================================================================

class AnnotationsManager:
    """
    Manages annotation storage and retrieval.
    Stores annotations as {text_id: [category1, category2, ...]}
    """

    @staticmethod
    def load_from_csv(filepath: str) -> Dict[str, List[str]]:
        """
        Load annotations from CSV file.

        Args:
            filepath: Path to CSV file (format: id;kategorie)

        Returns:
            Dictionary mapping text_id to list of categories
        """
        if not os.path.exists(filepath):
            return {}

        try:
            annotations = {}
            with open(filepath, 'r', encoding='utf-8') as f:
                # Skip header line
                next(f, None)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    # Split on first semicolon only
                    parts = line.split(';', 1)
                    if len(parts) == 2:
                        text_id, cats_str = parts
                        # Parse comma-separated categories
                        cats = [c.strip() for c in cats_str.split(',') if c.strip()]
                        annotations[text_id] = cats

            return annotations

        except Exception as e:
            st.error(f"Error loading annotations from {filepath}: {e}")
            return {}

    @staticmethod
    def save_to_csv(annotations: Dict[str, List[str]], filepath: str) -> bool:
        """
        Save annotations to CSV file.

        Uses direct file I/O instead of pandas for better performance.

        Args:
            annotations: Dictionary mapping text_id to list of categories
            filepath: Path where CSV should be saved

        Returns:
            True if save succeeded, False otherwise
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Write header
                f.write("id;kategorie\n")

                # Write each annotation
                for text_id, cats in annotations.items():
                    cats_str = ",".join(cats)
                    f.write(f"{text_id};{cats_str}\n")

            return True

        except Exception as e:
            st.error(f"Error saving annotations to {filepath}: {e}")
            return False

    @staticmethod
    def find_first_unannotated(texts_df: pd.DataFrame,
                               annotations: Dict[str, List[str]]) -> int:
        """
        Find the index of the first text without annotations.

        Args:
            texts_df: DataFrame of texts
            annotations: Current annotations dictionary

        Returns:
            Index of first unannotated text, or 0 if all are annotated
        """
        for i, row in texts_df.iterrows():
            text_id = str(row["id"])
            if text_id not in annotations or not annotations[text_id]:
                return i
        return 0

    @staticmethod
    def count_annotated(annotations: Dict[str, List[str]]) -> int:
        """
        Count how many texts have at least one category.

        Args:
            annotations: Annotations dictionary

        Returns:
            Number of texts with annotations
        """
        return sum(1 for cats in annotations.values() if cats)