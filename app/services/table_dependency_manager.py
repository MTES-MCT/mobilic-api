# from typing import Dict, List, Set
# from dataclasses import dataclass
# from sqlalchemy import text
# import logging

# logger = logging.getLogger(__name__)


# @dataclass
# class TableDependency:
#     name: str
#     depends_on: Set[str]
#     dependent_tables: Set[str]
#     level: int = 0


# class TableDependencyManager:
#     def __init__(self, db_session):
#         self.db = db_session
#         self.dependencies: Dict[str, TableDependency] = {}
#         self._load_dependencies()

#     def _load_dependencies(self):
#         """Load all table dependencies from database"""
#         query = """
#         WITH RECURSIVE fk_tree AS (
#             SELECT
#                 tc.table_name as dependent_table,
#                 ccu.table_name as referenced_table,
#                 0 as level
#             FROM information_schema.table_constraints tc
#             JOIN information_schema.constraint_column_usage ccu
#                 ON ccu.constraint_name = tc.constraint_name
#             WHERE tc.constraint_type = 'FOREIGN KEY'
#         )
#         SELECT DISTINCT
#             dependent_table,
#             referenced_table
#         FROM fk_tree;
#         """

#         results = self.db.execute(text(query)).fetchall()

#         for dep_table, ref_table in results:
#             if dep_table not in self.dependencies:
#                 self.dependencies[dep_table] = TableDependency(
#                     name=dep_table, depends_on=set(), dependent_tables=set()
#                 )
#             if ref_table not in self.dependencies:
#                 self.dependencies[ref_table] = TableDependency(
#                     name=ref_table, depends_on=set(), dependent_tables=set()
#                 )

#         for dep_table, ref_table in results:
#             self.dependencies[dep_table].depends_on.add(ref_table)
#             self.dependencies[ref_table].dependent_tables.add(dep_table)

#         self._calculate_levels()

#     def _calculate_levels(self):
#         """Calculate dependency levels for each table"""
#         changed = True
#         while changed:
#             changed = False
#             for table in self.dependencies.values():
#                 new_level = (
#                     max(
#                         (
#                             self.dependencies[dep].level
#                             for dep in table.depends_on
#                         ),
#                         default=-1,
#                     )
#                     + 1
#                 )
#                 if new_level != table.level:
#                     table.level = new_level
#                     changed = True

#     def get_anonymization_order(self) -> List[List[str]]:
#         """
#         Returns tables grouped by level in the order they should be anonymized
#         """
#         levels: Dict[int, List[str]] = {}
#         for table in self.dependencies.values():
#             if table.level not in levels:
#                 levels[table.level] = []
#             levels[table.level].append(table.name)

#         return [levels[level] for level in sorted(levels.keys())]

#     def get_table_dependencies(self, table_name: str) -> Set[str]:
#         """Get all dependencies for a specific table"""
#         if table_name not in self.dependencies:
#             return set()
#         return self.dependencies[table_name].depends_on
