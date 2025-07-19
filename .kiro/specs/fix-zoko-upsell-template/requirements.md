# Requirements Document

## Introduction

The Zoko upsell button template functionality is not working correctly. When users request specific products like "PAVO 90", the system should send a rich template with product image, name, description, and action button. However, currently it's only showing a simple button response instead of the full template with visual elements.

## Requirements

### Requirement 1

**User Story:** As a customer, I want to receive a rich product template with image and details when I request a specific product, so that I can see the product visually and get complete information before making a decision.

#### Acceptance Criteria

1. WHEN a user requests a specific product by name THEN the system SHALL return a rich template with product image, name, and action button
2. WHEN the template is sent THEN it SHALL include the product's actual image URL from the product data
3. WHEN the template is sent THEN it SHALL include the product's actual name and description
4. WHEN the template uses the zoko_upsell_product_01 template THEN it SHALL properly format all template arguments

### Requirement 2

**User Story:** As a customer, I want the product template to display correctly in WhatsApp, so that I can see the product information in a visually appealing format.

#### Acceptance Criteria

1. WHEN the template is sent THEN it SHALL use the correct Zoko template ID (zoko_upsell_product_01)
2. WHEN the template arguments are provided THEN they SHALL be in the correct order and format
3. WHEN the template is rendered THEN it SHALL show the header image, body text, and action button
4. IF the product has no image THEN the system SHALL use a default placeholder image

### Requirement 3

**User Story:** As a system administrator, I want to ensure the template data is properly structured, so that the Zoko API can process and display the template correctly.

#### Acceptance Criteria

1. WHEN building the template response THEN the system SHALL validate all required template arguments are present
2. WHEN the template response is created THEN it SHALL follow the exact JSON structure expected by Zoko
3. WHEN template arguments contain special characters THEN they SHALL be properly escaped or handled
4. IF any template argument is missing or invalid THEN the system SHALL use appropriate fallback values