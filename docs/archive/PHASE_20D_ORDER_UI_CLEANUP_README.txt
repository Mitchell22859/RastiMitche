Phase 20D — Order form cleanup and base-data simplification

Changes:
1. Admin order create date defaults to today's local Jalali date.
2. Subcategory management is removed from routed admin UI:
   - sidebar link removed
   - base-data dashboard card/stat removed
   - category quick links removed
   - tenant URL routes removed
   - admin subcategory view functions removed
3. /<company>/orders/create/ legacy route is removed. Admin order creation remains only at:
   /<company>/admin/orders/create/
4. Public request no longer prepares subcategory JSON.
5. Demo/Rasti seed commands no longer create subcategories.

Important:
- No database migration is required.
- The old subcategory database table and Order.service_subcategory field are intentionally left in place for backward compatibility and migration safety.
- To remove obsolete template files from your local project, run:
  .\scripts\phase20d_cleanup_removed_routes.ps1

After extracting:
python manage.py check
python manage.py runserver
