# PREDICT Failure Report Template

Copy everything below, fill in the blanks, and paste into chat:

```
---FAILURE REPORT---
Profile Name:
Car Number:
Phone:
Customer Issue:
Mechanic Analysis:
Confirmed Failure: yes/no
AI Predicted This: yes/no
Date:
Notes:
---END REPORT---
```

## Field Descriptions

| Field | Description | Example |
|-------|-------------|---------|
| Profile Name | Customer's name | Omar |
| Car Number | Vehicle plate/ID number | 36923 |
| Phone | Customer phone number | +974 5555 1234 |
| Customer Issue | What the customer reported | alternator problem |
| Mechanic Analysis | Actual diagnosis by mechanic | battery failure |
| Confirmed Failure | Was there a real failure? | yes or no |
| AI Predicted This | Did PREDICT AI predict this issue? | yes or no |
| Date | Date of the report | 2025-01-02 |
| Notes | Additional observations | Battery was weak, symptoms similar to alternator |

## Example (Filled In)

```
---FAILURE REPORT---
Profile Name: Omar
Car Number: 36923
Phone: +974 5555 1234
Customer Issue: alternator
Mechanic Analysis: battery
Confirmed Failure: yes
AI Predicted This: no
Date: 2025-01-02
Notes: Battery was weak, customer mistook symptoms for alternator
---END REPORT---
```

## How This Data Is Used

When you paste a completed template into the chat:
1. The system automatically parses the data
2. Shows you a confirmation dialog
3. Saves to training data if confirmed
4. This data helps improve AI prediction accuracy over time

## Tips

- Be specific in the Mechanic Analysis field
- Include relevant details in Notes
- Use consistent car number format
- Date should be YYYY-MM-DD format
