from sqlalchemy import Column, Integer, String, Float, ForeignKey, JSON
from app.core.database import Base


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, index=True)
    district = Column(String, index=True)
    urban_rural = Column(String)
    income_band = Column(String)
    household_size = Column(Integer)
    source_dataset = Column(String)
    source_year = Column(Integer)


class Individual(Base):
    __tablename__ = "individuals"

    id = Column(Integer, primary_key=True, index=True)
    household_id = Column(Integer, ForeignKey("households.id"), index=True)
    age = Column(Integer)
    gender = Column(String)
    education = Column(String)
    occupation = Column(String)
    digital_access_score = Column(Float)


class SyntheticProfile(Base):
    __tablename__ = "synthetic_profiles"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)
    attributes = Column(JSON)
    archetype_id = Column(Integer, nullable=True)


class Archetype(Base):
    __tablename__ = "archetypes"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)
    centroid_attributes = Column(JSON)
    population_weight = Column(Float)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String, primary_key=True, index=True)
    stimulus = Column(JSON)
    status = Column(String, default="pending")
    results = Column(JSON, nullable=True)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True)
    calibration_score = Column(Float)
    details = Column(JSON)


class FocusGroupSession(Base):
    __tablename__ = "focus_group_sessions"

    id = Column(String, primary_key=True, index=True)
    topic = Column(String)
    population_run_id = Column(String, index=True)
    status = Column(String, default="active")
    personas = Column(JSON)
    messages = Column(JSON, default=list)
    synthesis = Column(JSON, nullable=True)


class PricingOptimizationRun(Base):
    __tablename__ = "pricing_optimization_runs"

    id = Column(String, primary_key=True, index=True)
    product_concept = Column(String)
    category = Column(String)
    population_run_id = Column(String, index=True)
    currency = Column(String, default="INR")
    status = Column(String, default="pending")
    results = Column(JSON, nullable=True)
