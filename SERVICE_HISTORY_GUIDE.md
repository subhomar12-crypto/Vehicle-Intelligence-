# Service History & Component Tracking - User Guide

## Overview

The **Service History** tab is a powerful new feature that allows you to log actual service events for your vehicles and help the AI learn from real-world component lifecycles.

## Location

**Path:** Profiles → **Service History** (2nd tab)

## Why This Matters for AI

When you log service records with actual usage data, the AI can:

✅ **Learn real degradation patterns** - Not just theoretical lifespans
✅ **Improve predictions** - Based on YOUR specific driving and maintenance
✅ **Detect patterns** - e.g., "Brake pads last 60% longer with gentle driving"
✅ **Personalize recommendations** - Tailored to your vehicle and habits
✅ **Predict failures earlier** - By comparing expected vs. actual component life

---

## How to Use

### Step 1: Select Vehicle Profile

1. Click **"Service History"** tab
2. Select your vehicle from the dropdown at the top
3. The tab will load all service records for that vehicle

### Step 2: Log a New Service

Click the **"Log New Service"** tab and fill in the form:

#### Component Information
- **Component Type**: Select what was serviced (Brake Pads, Oil, Battery, etc.)
- **Service Type**: New replacement, inspection, repair, etc.

#### Service Details
- **Service Date**: When the service was performed
- **Odometer at Service**: Current km reading
- **Part Brand**: e.g., Bosch, Brembo, OEM
- **Part Specification**: e.g., Ceramic pads, 5W-30 oil

#### Expected Lifespan (IMPORTANT FOR AI)
- **Expected Lifespan (km)**: Manufacturer's rated lifespan
- **Expected Lifespan (months)**: Time-based lifespan

💡 **AI Learning**: The AI will compare this with actual usage to learn

#### Previous Component Info (If Replacement)
- **Actual Usage (km)**: How many km the old part lasted
- **Actual Usage (months)**: How many months it lasted
- **Condition**: How worn was it (100% = completely worn out)

💡 **AI Learning**: This is critical data! The AI compares expected vs. actual to learn degradation rates

#### Additional Information
- **Service Cost**: Optional, for your records
- **Technician/Location**: Who did the work
- **Notes**: Any observations, issues found, etc.

### Step 3: Save the Record

Click **"💾 Save Service Record"**

The AI now has this data to improve future predictions!

---

## Example Service Entry

Let's say you just replaced your front brake pads:

```
Component Type: Brake Pads (Front)
Service Type: Replacement (New)

Service Date: 2025-12-09
Odometer: 45,000 km
Part Brand: Brembo
Part Spec: Ceramic

Expected Lifespan: 80,000 km
Expected Lifespan: 36 months

---- Previous Component Info ----
Actual Usage: 42,000 km  (You installed them at 3,000 km)
Actual Usage: 28 months
Condition: Moderately Worn (50-79%)

Cost: $250
Technician: ABC Auto Garage
Notes: Front pads were at 3mm. Discs still good. No vibration issues.
```

### What the AI Learns:

✅ Your brake pads lasted 42,000 km (52% of expected 80,000 km)
✅ They were replaced at 50-79% wear
✅ AI updates its brake prediction model for similar conditions
✅ Next time, AI will predict replacement around 40,000-45,000 km, not 80,000 km

---

## Viewing Service History

Click the **"Service History"** tab to see all past services:

- Filter by component type
- See dates, mileage, costs
- Compare expected vs. actual usage
- Export to CSV (coming soon)

---

## Component Lifecycle Tracking

Click the **"Component Status"** tab to see currently installed components:

- Install date and mileage
- Current age (km and months)
- Current condition
- AI-predicted failure point
- Status (active/replaced)

---

## AI Learning Insights

Click the **"AI Learning Data"** tab and click **"Generate AI Analysis"**

You'll see what the AI has learned, for example:

```
Component: Brake Pads (Front)
  Total replacements logged: 3
  Average expected lifespan: 80,000 km
  Average actual usage: 45,000 km
  Lifespan accuracy: 56.3%

  ⚠️ AI learned: Component fails earlier than expected

  Recommendation: Predict replacement at ~45,000 km instead of 80,000 km
```

---

## Benefits Over Time

As you log more services:

1. **Month 1**: AI uses manufacturer defaults
2. **Month 3**: AI starts seeing patterns in your specific vehicle
3. **Month 6**: AI has learned your driving style impact
4. **Year 1**: AI provides highly personalized predictions
5. **Year 2+**: AI can predict component life with 90%+ accuracy

---

## Best Practices

### ✅ DO:
- Log every service, even small ones
- Record actual usage for replaced parts
- Be honest about condition at replacement
- Add notes about unusual wear patterns
- Update expected lifespans if using premium parts

### ❌ DON'T:
- Skip logging just because it's a small service
- Guess at numbers - use actual odometer readings
- Leave "Actual Usage" blank for replacements
- Ignore the "Condition" field

---

## Component Types Tracked

### Brake System
- Brake Pads (Front/Rear)
- Brake Discs (Front/Rear)

### Fluids
- Engine Oil
- Coolant
- Transmission Fluid
- Differential Oil

### Filters
- Oil Filter
- Air Filter
- Cabin Filter
- Fuel Filter

### Electrical
- Battery
- Alternator
- Starter Motor

### Engine
- Spark Plugs
- Timing Belt
- Serpentine Belt
- Water Pump

### Suspension & Tires
- Tires (Set or Individual)
- Suspension Components

### Other
- Custom components (use "Other")

---

## Integration with AI Predictions

The Service History data feeds into:

1. **Brake Wear Prediction** - Uses your actual brake pad lifespans
2. **Engine Health** - Tracks oil change patterns
3. **Battery Prediction** - Learns actual battery life in your climate
4. **Failure Forecast** - Predicts next failures based on your history
5. **Maintenance Scheduler** - Suggests service intervals based on your data

---

## Database Location

- **Service Records**: `./data/service_history.db`
- **Component Lifecycle**: Same database, separate table
- **Backup**: Automatically backed up with profiles

---

## Troubleshooting

### "No profiles found"
- Make sure you've created a vehicle profile first in the Profiles tab
- Click "Refresh Profiles" button

### "AI Analysis shows no data"
- Log at least one replacement service with actual usage data
- Inspections don't count - need replacement data for AI to learn

### "Can't save service record"
- Ensure vehicle profile is selected
- Check that odometer reading is valid
- Try refreshing the profiles list

---

## Future Enhancements

Coming soon:
- CSV export/import
- Service reminders based on your patterns
- Cost tracking and analytics
- Maintenance schedule optimization
- Multi-vehicle comparisons
- Cloud sync for service history

---

## Example Workflow

### Scenario: New Brake Pads Installed

1. Go to **Service History** tab
2. Select your vehicle profile
3. Click **"Log New Service"** tab
4. Fill in:
   - Component: Brake Pads (Front)
   - Service Type: Replacement (New)
   - Date: Today
   - Odometer: 45000 km
   - Brand: Brembo
   - Spec: Ceramic
   - Expected: 80000 km / 36 months
   - Old pads actual usage: 42000 km / 28 months
   - Condition: Moderately Worn (50-79%)
   - Cost: $250
   - Notes: "3mm remaining, replaced preventively"
5. Click **"Save Service Record"**

Now:
- Service is logged in history
- Component lifecycle updated (old marked as replaced, new marked as active)
- AI learns your brake pads last ~42k km, not 80k km
- Future predictions adjusted accordingly

---

## Summary

The Service History tab transforms your app from using generic manufacturer data to using **YOUR ACTUAL VEHICLE'S DATA**.

**The more services you log, the smarter the AI becomes!**

Every service record = Better predictions = Prevent unexpected breakdowns

---

**Happy tracking!** 🚗📊
