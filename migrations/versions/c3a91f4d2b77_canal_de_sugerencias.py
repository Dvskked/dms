"""canal de sugerencias de los jugadores

Revision ID: c3a91f4d2b77
Revises: 5ff67fb8fafa
Create Date: 2026-10-02 18:40:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'c3a91f4d2b77'
down_revision = '5ff67fb8fafa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from sqlalchemy import inspect

    # En desarrollo AUTO_CREATE_TABLES=1 ya pudo crear las tablas con db.create_all();
    # en ese caso la migracion solo marca su version y no rompe el arranque.
    existentes = set(inspect(op.get_bind()).get_table_names())

    if 'suggestions' not in existentes:
        op.create_table(
            'suggestions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=30), nullable=False),
            sa.Column('title', sa.String(length=120), nullable=False),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('status', sa.String(length=16), nullable=False),
            sa.Column('staff_reply', sa.Text(), nullable=True),
            sa.Column('replied_at', sa.DateTime(), nullable=True),
            sa.Column('replied_by_id', sa.Integer(), nullable=True),
            sa.Column('likes', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.CheckConstraint("status in ('new','reviewing','done')", name='suggestion_status_valid'),
            sa.ForeignKeyConstraint(['replied_by_id'], ['users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_suggestions_category'), 'suggestions', ['category'], unique=False)
        op.create_index(op.f('ix_suggestions_created_status'), 'suggestions', ['created_at', 'status'], unique=False)
        op.create_index(op.f('ix_suggestions_status'), 'suggestions', ['status'], unique=False)
        op.create_index(op.f('ix_suggestions_user_id'), 'suggestions', ['user_id'], unique=False)

    if 'suggestion_votes' not in existentes:
        op.create_table(
            'suggestion_votes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('suggestion_id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['suggestion_id'], ['suggestions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('suggestion_id', 'user_id', name='uq_suggestion_vote'),
        )
        op.create_index(op.f('ix_suggestion_votes_suggestion_id'), 'suggestion_votes', ['suggestion_id'], unique=False)
        op.create_index(op.f('ix_suggestion_votes_user_id'), 'suggestion_votes', ['user_id'], unique=False)


def downgrade() -> None:
    from sqlalchemy import inspect

    existentes = set(inspect(op.get_bind()).get_table_names())

    if 'suggestion_votes' in existentes:
        op.drop_index(op.f('ix_suggestion_votes_user_id'), table_name='suggestion_votes')
        op.drop_index(op.f('ix_suggestion_votes_suggestion_id'), table_name='suggestion_votes')
        op.drop_table('suggestion_votes')

    if 'suggestions' in existentes:
        op.drop_index(op.f('ix_suggestions_user_id'), table_name='suggestions')
        op.drop_index(op.f('ix_suggestions_status'), table_name='suggestions')
        op.drop_index(op.f('ix_suggestions_created_status'), table_name='suggestions')
        op.drop_index(op.f('ix_suggestions_category'), table_name='suggestions')
        op.drop_table('suggestions')
