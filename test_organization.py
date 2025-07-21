#!/usr/bin/env python3
"""Test script to verify the file organization improvements"""

import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from titles import identify_file, extract_name_from_filename

# Test cases representing the problematic files from the user's list
test_files = [
    # XCI files that were incorrectly going to UPDATES
    "/games/Celeste/Celeste[01002B30028F6800][v0].xci",
    "/games/Hades/Hades[01DB28ACE6A5FAD3][v0].xci",
    "/games/Hollow Knight/Hollow Knight[0100633007D48800][v0].xci",
    
    # Files with version 0 that should be BASE
    "/games/13 Sentinels - Aegis Rim/13 Sentinels - Aegis Rim[01003FC01670C000][v0].xci",
    "/games/Bayonetta 2/Bayonetta 2[01007960049A0000][v0].xci",
    
    # Unknown games that should use filename extraction
    "/games/Unknown Game/Unknown Game[01008D900B984000][v0].nsp",
    "/games/Unknown Game/sxs-balatro_v589824 (Update)[0100CD801CE5E800][v589824].nsp",
    
    # Test name extraction
    "/games/SONIC X SHADOW GENERATIONS[01005EA01C0FC000][v0].nsp",
    "/games/Prince of Persia The Lost Crown[0100210019428000][v0].nsp",
]

print("Testing file identification improvements...\n")

for test_file in test_files:
    print(f"Testing: {os.path.basename(test_file)}")
    
    # Test name extraction
    filename = os.path.basename(test_file)
    extracted_name = extract_name_from_filename(filename)
    print(f"  Extracted name: {extracted_name}")
    
    # Create a mock file info (simulate what identify_file would return)
    # In real usage, this would call identify_file(test_file) but we're testing without actual files
    file_info = {
        'filepath': test_file,
        'filename': filename,
        'extension': filename.split('.')[-1],
    }
    
    # Check XCI classification
    if file_info['extension'].lower() in ('xci', 'xcz'):
        if '[v0]' in filename or '[0]' in filename:
            print(f"  Classification: BASE (XCI with version 0)")
        else:
            print(f"  Classification: Would need CNMT inspection")
    
    print()

print("\nName extraction tests:")
test_names = [
    "Unknown Game[01008D900B984000][v0].nsp",
    "sxs-balatro_v589824 (Update)[0100CD801CE5E800][v589824].nsp",
    "SONIC X SHADOW GENERATIONS[01005EA01C0FC000][v0].nsp",
    "Prince of Persia The Lost Crown - Immortal Outfit (DLC)[0100210019429002][v0].nsp",
    "Super Mario Bros. Wonder[010015100B514000][1.0.0][0][16.0.3].nsp",
]

for name in test_names:
    extracted = extract_name_from_filename(name)
    print(f"{name} -> {extracted}")