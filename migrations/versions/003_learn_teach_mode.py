# migrations/versions/003_learn_teach_mode.py
"""Learn/Teach Mode Migration

Revision ID: 003
Revises: 002
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    # Create enum types
    op.execute("CREATE TYPE profilemode AS ENUM ('learner', 'teacher', 'both')")
    op.execute("CREATE TYPE pricetype AS ENUM ('hourly', 'fixed', 'free')")
    
    # Add new columns to users table
    op.add_column('users', sa.Column('profile_mode', sa.Enum('learner', 'teacher', 'both', name='profilemode'), nullable=False, server_default='both'))
    op.add_column('users', sa.Column('headline', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('location', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('website', sa.String(200), nullable=True))
    op.add_column('users', sa.Column('open_to_work', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('users', sa.Column('open_to_freelance', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('users', sa.Column('hourly_rate', sa.DECIMAL(10,2), nullable=True))
    op.add_column('users', sa.Column('response_time', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('success_rate', sa.Integer(), nullable=True))
    
    # Create skills table
    op.create_table('skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('category', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Create user_skills table
    op.create_table('user_skills',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.Column('proficiency', sa.String(20), nullable=True),
        sa.Column('years_experience', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create services table
    op.create_table('services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price_type', sa.Enum('hourly', 'fixed', 'free', name='pricetype'), nullable=False),
        sa.Column('price_amount', sa.DECIMAL(10,2), nullable=True),
        sa.Column('duration', sa.String(50), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create learning_goals table
    op.create_table('learning_goals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('budget_min', sa.DECIMAL(10,2), nullable=True),
        sa.Column('budget_max', sa.DECIMAL(10,2), nullable=True),
        sa.Column('timeline', sa.String(50), nullable=True),
        sa.Column('preferred_format', sa.String(50), nullable=True),
        sa.Column('status', sa.String(20), nullable=True, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create reviews table
    op.create_table('reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reviewer_id', sa.Integer(), nullable=False),
        sa.Column('reviewee_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('service_type', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewee_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reviewer_id', 'reviewee_id', 'service_type', name='unique_review')
    )
    
    # Create indexes for better performance
    op.create_index('ix_services_user_id', 'services', ['user_id'])
    op.create_index('ix_learning_goals_user_id', 'learning_goals', ['user_id'])
    op.create_index('ix_user_skills_user_id', 'user_skills', ['user_id'])
    op.create_index('ix_reviews_reviewee_id', 'reviews', ['reviewee_id'])

def downgrade():
    # Drop indexes
    op.drop_index('ix_reviews_reviewee_id')
    op.drop_index('ix_user_skills_user_id')
    op.drop_index('ix_learning_goals_user_id')
    op.drop_index('ix_services_user_id')
    
    # Drop tables
    op.drop_table('reviews')
    op.drop_table('learning_goals')
    op.drop_table('services')
    op.drop_table('user_skills')
    op.drop_table('skills')
    
    # Drop columns from users table
    op.drop_column('users', 'success_rate')
    op.drop_column('users', 'response_time')
    op.drop_column('users', 'hourly_rate')
    op.drop_column('users', 'open_to_freelance')
    op.drop_column('users', 'open_to_work')
    op.drop_column('users', 'website')
    op.drop_column('users', 'location')
    op.drop_column('users', 'summary')
    op.drop_column('users', 'headline')
    op.drop_column('users', 'profile_mode')
    
    # Drop enum types
    op.execute("DROP TYPE pricetype")
    op.execute("DROP TYPE profilemode")