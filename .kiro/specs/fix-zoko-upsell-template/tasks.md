# Implementation Plan

- [-] 1. Analyze the current template formatting in handoff_tools.py
  - Examine how templates are currently constructed
  - Identify why the rich template is not displaying correctly
  - _Requirements: 1.1, 2.1, 3.2_

- [ ] 2. Debug the template structure for zoko_upsell_product_01
  - [ ] 2.1 Add logging to capture the exact template structure being sent
    - Add detailed logging of template arguments and structure
    - Verify template_id is correctly set to "zoko_upsell_product_01"
    - _Requirements: 2.1, 3.1_
  
  - [ ] 2.2 Compare template structure with Zoko's expected format
    - Verify the JSON structure matches what Zoko expects
    - Check if isRichTemplate flag is needed in the response
    - _Requirements: 2.2, 3.2_

- [ ] 3. Fix the template formatting in search_products_with_handoff_func
  - [ ] 3.1 Update the template structure to match Zoko's requirements
    - Ensure whatsapp_type is correctly set to "buttonTemplate"
    - Verify template_id is correctly set to "zoko_upsell_product_01"
    - _Requirements: 1.1, 2.1, 3.2_
  
  - [ ] 3.2 Ensure template arguments are correctly ordered and formatted
    - Verify image_url is the first argument
    - Verify product name is the second argument
    - Verify order text is the third argument
    - Verify product URL is the fourth argument
    - _Requirements: 1.2, 1.3, 2.2_

- [ ] 4. Implement validation and fallback values
  - [ ] 4.1 Add validation for required template arguments
    - Check if all required arguments are present
    - Log warnings for missing arguments
    - _Requirements: 3.1_
  
  - [ ] 4.2 Add fallback values for missing or invalid data
    - Use default placeholder image if image_url is missing
    - Use generic product name if name is missing
    - Use generic order text if order text is missing
    - Use default URL if product URL is missing
    - _Requirements: 2.4, 3.4_

- [ ] 5. Fix the template formatting in search_one_product_with_handoff_func
  - Apply the same fixes as in search_products_with_handoff_func
  - Ensure consistent template formatting across functions
  - _Requirements: 1.1, 2.1, 3.2_

- [ ] 6. Fix the template formatting in get_property_details_with_handoff_func
  - Apply the same fixes as in search_products_with_handoff_func
  - Ensure consistent template formatting across functions
  - _Requirements: 1.1, 2.1, 3.2_

- [ ] 7. Handle special characters in template arguments
  - Implement proper escaping for special characters
  - Test with product names containing special characters
  - _Requirements: 3.3_

- [ ] 8. Write unit tests for template formatting
  - Test with various product data inputs
  - Test with missing or invalid product data
  - Verify template structure matches Zoko's requirements
  - _Requirements: 1.4, 2.3, 3.1_

- [ ] 9. Test the fix with real product queries
  - Test with "PAVO 90" and other specific products
  - Verify the template displays correctly in WhatsApp
  - _Requirements: 1.1, 2.3_