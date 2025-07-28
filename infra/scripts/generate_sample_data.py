#!/usr/bin/env python3
"""
Generate sample parquet data for maritime shipping data lake.
Creates fake data for ship parts, food inventory, vessels, and shipments.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
from faker import Faker
import argparse

# Add the script directory to path to ensure imports work
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(script_dir)

def setup_faker():
    """Initialize Faker with providers"""
    fake = Faker()
    Faker.seed(42)  # For reproducible data
    random.seed(42)
    np.random.seed(42)
    return fake

def generate_ship_parts_data(fake, num_records=1000):
    """Generate ship parts inventory data"""
    
    # Maritime-specific part categories and names
    part_categories = [
        'Engine Components', 'Navigation Equipment', 'Safety Equipment',
        'Deck Hardware', 'Hull Components', 'Electrical Systems',
        'Fuel Systems', 'Propulsion', 'Communication Equipment'
    ]
    
    part_names = [
        'Marine Diesel Engine', 'Propeller Shaft', 'Rudder Assembly',
        'Anchor Chain', 'Life Raft', 'GPS Navigation System',
        'Radar Antenna', 'Emergency Beacon', 'Fuel Pump',
        'Bilge Pump', 'Windlass', 'Bow Thruster',
        'Marine Battery', 'VHF Radio', 'Compass',
        'Fire Suppression System', 'Hull Plate', 'Winch Motor',
        'Ship Bell', 'Mooring Line', 'Cargo Hatch Cover',
        'Ballast Tank Valve', 'Steering Gear', 'Engine Room Fan'
    ]
    
    suppliers = [
        'Maritime Solutions Inc', 'Ocean Tech Supply', 'Neptune Marine Parts',
        'Poseidon Components', 'Tidal Equipment Co', 'Deep Sea Supply',
        'Maritime Power Systems', 'Coastal Marine Parts', 'Blue Water Supply'
    ]
    
    statuses = ['In Stock', 'Low Stock', 'Out of Stock', 'On Order', 'Discontinued']
    
    data = []
    for i in range(num_records):
        part_id = f"PART-{str(i+1).zfill(6)}"
        
        data.append({
            'part_id': part_id,
            'part_name': random.choice(part_names),
            'category': random.choice(part_categories),
            'supplier': random.choice(suppliers),
            'unit_cost': round(random.uniform(50.0, 15000.0), 2),
            'quantity_in_stock': random.randint(0, 500),
            'reorder_level': random.randint(5, 50),
            'weight_kg': round(random.uniform(0.5, 2000.0), 2),
            'status': random.choice(statuses),
            'last_updated': fake.date_between(start_date='-1y', end_date='today'),
            'warehouse_location': f"WH-{random.randint(1, 10)}-{random.choice(['A', 'B', 'C'])}-{random.randint(1, 20)}"
        })
    
    return pd.DataFrame(data)

def generate_food_inventory_data(fake, num_records=500):
    """Generate food inventory data including hot dogs and chicken tenders"""
    
    food_types = [
        'hot_dogs', 'chicken_tenders', 'beef_stew', 'fish_fillets',
        'canned_beans', 'rice', 'pasta', 'bread', 'milk', 'cheese',
        'eggs', 'bacon', 'sausages', 'potatoes', 'onions', 'carrots',
        'frozen_vegetables', 'canned_soup', 'coffee', 'tea'
    ]
    
    storage_types = ['Frozen', 'Refrigerated', 'Dry Storage', 'Canned']
    suppliers = [
        'Maritime Food Services', 'Ocean Fresh Supply', 'Galley Provisions',
        'Sea Cook Supply', 'Marine Catering Co', 'Shipboard Food Systems'
    ]
    
    data = []
    for i in range(num_records):
        food_type = random.choice(food_types)
        
        # Assign realistic storage types based on food
        if food_type in ['hot_dogs', 'chicken_tenders', 'beef_stew', 'fish_fillets', 'frozen_vegetables']:
            storage_type = 'Frozen'
        elif food_type in ['milk', 'cheese', 'eggs', 'bacon']:
            storage_type = 'Refrigerated'
        elif food_type in ['canned_beans', 'canned_soup']:
            storage_type = 'Canned'
        else:
            storage_type = 'Dry Storage'
        
        data.append({
            'inventory_id': f"FOOD-{str(i+1).zfill(6)}",
            'shipment_id': f"SHIP-{random.randint(1, 100):06d}",
            'food_type': food_type,
            'quantity': random.randint(10, 1000),
            'unit': random.choice(['kg', 'lbs', 'cases', 'boxes', 'units']),
            'storage_type': storage_type,
            'supplier': random.choice(suppliers),
            'unit_cost': round(random.uniform(2.0, 50.0), 2),
            'expiry_date': fake.date_between(start_date='today', end_date='+2y'),
            'storage_location': f"GALLEY-{random.randint(1, 5)}-{random.choice(['A', 'B', 'C'])}"
        })
    
    return pd.DataFrame(data)

def generate_vessels_data(fake, num_records=50):
    """Generate vessel fleet data"""
    
    vessel_types = [
        'Container Ship', 'Bulk Carrier', 'Tanker', 'Cargo Ship',
        'Ferry', 'Tugboat', 'Supply Vessel', 'Research Vessel'
    ]
    
    vessel_names = [
        'Sea Wanderer', 'Ocean Pioneer', 'Maritime Star', 'Deep Explorer',
        'Tidal Force', 'Neptune\'s Pride', 'Wave Runner', 'Coral Princess',
        'Storm Chaser', 'Blue Horizon', 'Sea Guardian', 'Ocean Spirit',
        'Maritime Glory', 'Poseidon\'s Reach', 'Tidal Surge', 'Deep Current'
    ]
    
    flags = ['USA', 'Panama', 'Liberia', 'Marshall Islands', 'Singapore', 'Norway', 'UK']
    statuses = ['Active', 'In Port', 'Under Maintenance', 'Dry Dock', 'En Route']
    
    data = []
    for i in range(num_records):
        vessel_type = random.choice(vessel_types)
        
        data.append({
            'vessel_id': f"VSL-{str(i+1).zfill(4)}",
            'vessel_name': f"{random.choice(vessel_names)} {random.randint(1, 99)}",
            'vessel_type': vessel_type,
            'flag_state': random.choice(flags),
            'gross_tonnage': random.randint(1000, 200000),
            'length_m': random.randint(50, 400),
            'beam_m': random.randint(10, 60),
            'crew_capacity': random.randint(15, 150),
            'cargo_capacity_tons': random.randint(500, 100000),
            'built_year': random.randint(1990, 2023),
            'status': random.choice(statuses),
            'current_port': fake.city(),
            'imo_number': f"IMO{random.randint(1000000, 9999999)}"
        })
    
    return pd.DataFrame(data)

def generate_shipments_data(fake, vessel_ids, num_records=200):
    """Generate shipment/logistics data"""
    
    ports = [
        'Los Angeles', 'Long Beach', 'New York', 'Savannah', 'Norfolk',
        'Charleston', 'Houston', 'Seattle', 'Oakland', 'Miami',
        'Rotterdam', 'Hamburg', 'Antwerp', 'Singapore', 'Shanghai'
    ]
    
    cargo_types = [
        'Containers', 'Bulk Cargo', 'Liquid Cargo', 'Break Bulk',
        'Heavy Lift', 'Refrigerated Cargo', 'Dangerous Goods'
    ]
    
    statuses = ['Loading', 'In Transit', 'Discharged', 'Delayed', 'Completed']
    
    data = []
    for i in range(num_records):
        departure_date = fake.date_between(start_date='-6m', end_date='+3m')
        arrival_date = departure_date + timedelta(days=random.randint(1, 30))
        
        data.append({
            'shipment_id': f"SHIP-{str(i+1).zfill(6)}",
            'vessel_id': random.choice(vessel_ids),
            'origin_port': random.choice(ports),
            'destination_port': random.choice(ports),
            'cargo_type': random.choice(cargo_types),
            'cargo_weight_tons': random.randint(100, 50000),
            'cargo_value_usd': random.randint(100000, 10000000),
            'departure_date': departure_date,
            'scheduled_arrival_date': arrival_date,
            'actual_arrival_date': arrival_date + timedelta(days=random.randint(-2, 5)) if random.random() > 0.3 else None,
            'status': random.choice(statuses),
            'shipping_line': random.choice(['Maersk', 'MSC', 'COSCO', 'CMA CGM', 'Hapag-Lloyd']),
            'bill_of_lading': f"BOL{random.randint(100000, 999999)}"
        })
    
    return pd.DataFrame(data)

def save_as_parquet(df, filename, output_dir):
    """Save DataFrame as parquet file"""
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, f"{filename}.parquet")
    df.to_parquet(filepath, index=False)
    print(f"✅ Generated {filepath} with {len(df)} records")
    return filepath

def main():
    parser = argparse.ArgumentParser(description='Generate sample maritime shipping data')
    parser.add_argument('--output-dir', default='../data', help='Output directory for parquet files')
    parser.add_argument('--ship-parts', type=int, default=1000, help='Number of ship parts records')
    parser.add_argument('--food-inventory', type=int, default=500, help='Number of food inventory records')
    parser.add_argument('--vessels', type=int, default=50, help='Number of vessel records')
    parser.add_argument('--shipments', type=int, default=200, help='Number of shipment records')
    
    args = parser.parse_args()
    
    print("🚢 Generating maritime shipping sample data...")
    
    fake = setup_faker()
    
    # Generate ship parts data
    print("📦 Generating ship parts inventory...")
    ship_parts_df = generate_ship_parts_data(fake, args.ship_parts)
    save_as_parquet(ship_parts_df, 'ship_parts', args.output_dir)
    
    # Generate food inventory data
    print("🍖 Generating food inventory...")
    food_df = generate_food_inventory_data(fake, args.food_inventory)
    save_as_parquet(food_df, 'food_inventory', args.output_dir)
    
    # Generate vessels data
    print("⚓ Generating vessels data...")
    vessels_df = generate_vessels_data(fake, args.vessels)
    save_as_parquet(vessels_df, 'vessels', args.output_dir)
    
    # Generate shipments data (using vessel IDs from vessels data)
    print("📋 Generating shipments data...")
    vessel_ids = vessels_df['vessel_id'].tolist()
    shipments_df = generate_shipments_data(fake, vessel_ids, args.shipments)
    save_as_parquet(shipments_df, 'shipments', args.output_dir)
    
    print(f"\n🎉 Successfully generated all sample data in {args.output_dir}/")
    print("\n📊 Data Summary:")
    print(f"  • Ship Parts: {len(ship_parts_df)} records")
    print(f"  • Food Inventory: {len(food_df)} records")
    print(f"  • Vessels: {len(vessels_df)} records")
    print(f"  • Shipments: {len(shipments_df)} records")
    
    # Show some sample data
    print("\n🔍 Sample Hot Dogs & Chicken Tenders:")
    food_sample = food_df[food_df['food_type'].isin(['hot_dogs', 'chicken_tenders'])].head(3)
    print(food_sample[['food_type', 'quantity', 'unit', 'supplier', 'storage_type']].to_string(index=False))

if __name__ == "__main__":
    main() 