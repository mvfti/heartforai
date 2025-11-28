"""Data generator for synthetic insurance policy holders using Mimesis."""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from mimesis.locales import Locale  

from mimesis import Datetime, Numeric, Person, Address
from models import PolicyHolder


# Belgian postal code ranges
FLANDERS_POSTCODES = list(range(1500, 2000)) + list(range(2200, 3000)) + list(range(3000, 4000)) + \
                     list(range(8000, 10000))
WALLONIA_POSTCODES = list(range(1300, 1500)) + list(range(4000, 8000))
BRUSSELS_POSTCODES = list(range(1000, 1300))

# Insurance products based on Belfius Home Insurance
PRODUCTS = [
    {
        "product_id": "2178",
        "product_name": "Home Insurance - Base",
        "coverages": ["Fire", "Water Damage", "Storm", "Natural Disasters"],
        "base_premium": 350.0
    },
    {
        "product_id": "2179",
        "product_name": "Home Insurance - Theft",
        "coverages": ["Fire", "Water Damage", "Storm", "Theft", "Vandalism"],
        "base_premium": 520.0
    },
    {
        "product_id": "2180",
        "product_name": "Home Insurance - Complete",
        "coverages": ["Fire", "Water Damage", "Storm", "Theft", "Glass Breakage", "Natural Disasters"],
        "base_premium": 680.0
    },
    {
        "product_id": "2181",
        "product_name": "Home Insurance - Premium",
        "coverages": ["Fire", "Water Damage", "Storm", "Theft", "Glass Breakage", "Natural Disasters", "Legal Protection"],
        "base_premium": 850.0
    },
    {
        "product_id": "2182",
        "product_name": "Tenant Insurance - Basic",
        "coverages": ["Fire", "Water Damage", "Civil Liability"],
        "base_premium": 180.0
    },
    {
        "product_id": "2183",
        "product_name": "Tenant Insurance - Plus",
        "coverages": ["Fire", "Water Damage", "Theft", "Civil Liability"],
        "base_premium": 280.0
    },
]


class PolicyDataGenerator:
    """Generate synthetic insurance policy holder data."""

    def __init__(self, seed: int = 42):
        """Initialize the data generator with a seed for reproducibility."""
        random.seed(seed)
        self.datetime_generator = Datetime(seed=seed)
        self.numeric_generator = Numeric(seed=seed)
        self.person_nl = Person(locale='nl', seed=seed)
        self.person_fr = Person(locale='fr', seed=seed)
        self.address_nl = Address(locale=Locale.NL_BE, seed=seed) 
        self.address_fr = Address(locale=Locale.NL_BE, seed=seed)

    def _get_postal_code_and_language(self) -> tuple[str, str]:
        """
        Generate a Belgian postal code and corresponding language.

        Distribution:
        - 40% Flanders (NL)
        - 40% Wallonia (FR)
        - 20% Brussels (NL or FR)

        Returns:
            Tuple of (postal_code, language)
        """
        rand = random.random()

        if rand < 0.4:  # Flanders
            postal_code = str(random.choice(FLANDERS_POSTCODES)).zfill(4)
            language = "NL"
        elif rand < 0.8:  # Wallonia
            postal_code = str(random.choice(WALLONIA_POSTCODES)).zfill(4)
            language = "FR"
        else:  # Brussels
            postal_code = str(random.choice(BRUSSELS_POSTCODES)).zfill(4)
            language = random.choice(["NL", "FR"])

        return postal_code, language

    def _generate_policy_id(self) -> str:
        """Generate a 9-digit policy ID."""
        # Start with 900 as per example
        prefix = "900"
        suffix = str(self.numeric_generator.integer_number(start=100000, end=999999))
        return prefix + suffix

    def _generate_dates(self) -> tuple[datetime, datetime]:
        """
        Generate policy start and end dates.

        Policy end date must be at least one year after start date.

        Returns:
            Tuple of (start_date, end_date)
        """
        # Generate start dates within the last 3 years to present
        start_date = self.datetime_generator.datetime(
            start=2022,
            end=2025
        )

        # End date is 1-3 years after start date
        years_duration = random.choice([1, 2, 3])
        end_date = start_date + timedelta(days=365 * years_duration)

        return start_date, end_date

    def _calculate_premium(self, base_premium: float, postal_code: str) -> float:
        """
        Calculate premium with regional adjustments.

        Args:
            base_premium: Base premium amount
            postal_code: Belgian postal code

        Returns:
            Adjusted premium amount
        """
        # Add some randomness to premiums (+/- 20%)
        variation = random.uniform(0.8, 1.2)
        premium = base_premium * variation

        # Round to 2 decimal places
        return round(premium, 2)

    def _generate_date_of_birth(self) -> datetime:
        """
        Generate a date of birth for an adult (18-80 years old).

        Returns:
            Date of birth
        """
        # Generate birth dates for adults aged 18-80
        current_year = datetime.now().year
        birth_year_start = current_year - 80
        birth_year_end = current_year - 18

        return self.datetime_generator.datetime(
            start=birth_year_start,
            end=birth_year_end
        )

    def generate_policy_holder(self) -> PolicyHolder:
        """
        Generate a single synthetic policy holder record.

        Returns:
            PolicyHolder instance with synthetic data
        """
        # Select random product
        product = random.choice(PRODUCTS)

        # Get postal code and language
        postal_code, language = self._get_postal_code_and_language()

        # Generate client information based on language
        if language == "NL":
            client_name = self.person_nl.full_name()
            street = self.address_nl.street_name()
            street_number = self.address_nl.street_number()
            city = self.address_nl.city()
        else:  # FR
            client_name = self.person_fr.full_name()
            street = self.address_fr.street_name()
            street_number = self.address_fr.street_number()
            city = self.address_fr.city()

        # Format address
        address = f"{street} {street_number}, {postal_code} {city}"

        # Generate date of birth
        date_of_birth = self._generate_date_of_birth()

        # Generate dates
        start_date, end_date = self._generate_dates()

        # Calculate premium
        premium = self._calculate_premium(product["base_premium"], postal_code)

        # Create coverage description
        coverage_desc = ", ".join(product["coverages"])

        return PolicyHolder(
            policy_id=self._generate_policy_id(),
            client_name=client_name,
            address=address,
            date_of_birth=date_of_birth,
            product_id=product["product_id"],
            product_name=product["product_name"],
            coverage_desc=coverage_desc,
            policy_start_dt=start_date,
            policy_end_dt=end_date,
            premium_amt=premium,
            language=language,
            postal_code=postal_code
        )

    def generate_batch(self, count: int) -> List[PolicyHolder]:
        """
        Generate multiple policy holder records.

        Args:
            count: Number of records to generate

        Returns:
            List of PolicyHolder instances
        """
        return [self.generate_policy_holder() for _ in range(count)]

    def save_to_json(self, policy_holders: List[PolicyHolder], output_path: str | Path):
        """
        Save policy holders to JSON file.

        Args:
            policy_holders: List of PolicyHolder instances
            output_path: Path to output JSON file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict format for JSON serialization
        data = []
        for ph in policy_holders:
            record = {
                "policy_id": ph.policy_id,
                "client_name": ph.client_name,
                "address": ph.address,
                "date_of_birth": ph.date_of_birth.strftime("%Y-%m-%d"),
                "product_id": ph.product_id,
                "product_name": ph.product_name,
                "coverage_desc": ph.coverage_desc,
                "policy_start_dt": ph.policy_start_dt.strftime("%Y-%m-%d"),
                "policy_end_dt": ph.policy_end_dt.strftime("%Y-%m-%d"),
                "premium_amt": ph.premium_amt,
                "language": ph.language,
                "postal_code": ph.postal_code
            }
            data.append(record)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Successfully saved {len(policy_holders)} policy holders to {output_path}")


def main():
    """Main function to generate synthetic data."""
    generator = PolicyDataGenerator(seed=42)

    # Generate 1000 policy holders
    print("Generating 1000 synthetic policy holders...")
    policy_holders = generator.generate_batch(1000)

    # Save to JSON
    output_path = Path("database/db.json")
    generator.save_to_json(policy_holders, output_path)

    # Print statistics
    print("\nGeneration Statistics:")
    print(f"Total records: {len(policy_holders)}")

    # Language distribution
    languages = {}
    for ph in policy_holders:
        languages[ph.language] = languages.get(ph.language, 0) + 1
    print("\nLanguage Distribution:")
    for lang, count in sorted(languages.items()):
        print(f"  {lang}: {count} ({count/len(policy_holders)*100:.1f}%)")

    # Product distribution
    products = {}
    for ph in policy_holders:
        products[ph.product_name] = products.get(ph.product_name, 0) + 1
    print("\nProduct Distribution:")
    for product, count in sorted(products.items()):
        print(f"  {product}: {count} ({count/len(policy_holders)*100:.1f}%)")

    # Premium statistics
    premiums = [ph.premium_amt for ph in policy_holders]
    print("\nPremium Statistics:")
    print(f"  Min: €{min(premiums):.2f}")
    print(f"  Max: €{max(premiums):.2f}")
    print(f"  Average: €{sum(premiums)/len(premiums):.2f}")


if __name__ == "__main__":
    main()
