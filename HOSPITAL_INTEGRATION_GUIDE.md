# Hospital Integration Module - Complete Guide

## Overview
The Organ Donation System now includes a comprehensive **Hospital Integration Module** that manages the entire workflow from death reporting to organ harvesting and recipient notification.

## Hospital–AI Integration Flow
This system integrates hospital workflows with the AI matching engine and admin oversight to ensure safe, fair, and timely organ allocation. Key interactions:

- Donor → Hospital: Donors register and hospitals verify eligibility, report deaths, and harvest organs.
- Hospital → AI System: Hospitals feed verified data into the AI, which runs smart matching algorithms and detects anomalies.
- AI System → Admin: AI suggests matches and analytics; admins validate hospital actions and oversee transparency.
- Admin → Recipient: Admin ensures recipients get accurate, real-time notifications and status updates.
- Recipient → Hospital: Recipients confirm acceptance, and hospitals coordinate the transplant surgery.
- Feedback Loops: AI sends notifications directly to recipients, and hospitals receive anomaly alerts for safety.

For an overall visual of these interactions, see the system-wide flow diagram in the Complete System Overview.
## Features Added

### 1. **Hospital Management System**
- Hospital registration with medical council verification
- Secure hospital login and dashboard
- Hospital profile management

### 2. **Death Reporting Workflow**
- Report donor death with medical details
- Capture next-of-kin information
- Automatic WhatsApp notification to next of kin
- Medical certificate tracking

### 3. **Medical Verification System**
- Verify death reports with medical findings
- Assess organ viability
- Document verification notes
- Status tracking (Reported → Verified → Organs-Ready → Completed)

### 4. **Organ Harvesting Management**
- Record organs successfully harvested
- Update organ status in system
- Automatic notification to matching recipients
- Real-time availability updates

### 5. **Hospital Dashboard**
- View all death reports
- Track report status
- Analytics: total reports, pending verifications, harvested organs
- Action buttons for verification and harvesting

## Database Schema

### Hospital Model
```python
class Hospital(db.Model):
    - id (Primary Key)
    - hospital_name (Unique)
    - registration_number (Unique)
    - mobile (Unique)
    - email (Unique)
    - address
    - city
    - state
    - license_verified (Boolean)
    - password (Hashed)
    - created_at (Timestamp)
```

### DeathReport Model
```python
class DeathReport(db.Model):
    - id (Primary Key)
    - donor_id (Foreign Key → Donor)
    - hospital_id (Foreign Key → Hospital)
    - death_time (DateTime)
    - cause_of_death
    - medical_cert_number
    - status (Reported/Verified/Organs-Ready/Completed)
    - next_of_kin_name
    - next_of_kin_mobile
    - next_of_kin_relation
    - organs_harvested (Comma-separated)
    - harvested_at (DateTime)
    - notes (Medical notes)
    - reported_at (Timestamp)
    - verified_at (DateTime)
```

## API Routes

### Hospital Authentication
- `POST /hospital/register` - Register new hospital
- `POST /hospital/login` - Hospital login
- `GET /hospital/logout` - Logout

### Hospital Dashboard & Operations
- `GET /hospital/dashboard` - View hospital dashboard
- `GET /hospital/report_death` - Death report form
- `POST /hospital/report_death` - Submit death report
- `GET /hospital/verify_death/<report_id>` - Verify death form
- `POST /hospital/verify_death/<report_id>` - Confirm verification
- `GET /hospital/harvest_organs/<report_id>` - Organ harvesting form
- `POST /hospital/harvest_organs/<report_id>` - Record organ harvest

## Workflow: Death to Transplant

### Step 1: Death Reporting
1. Hospital staff logs in to system
2. Navigates to "Report Death"
3. Enters donor mobile number (searches registered donors)
4. Fills in death details:
   - Time of death
   - Cause of death
   - Medical certificate number
   - Next of kin information
5. System automatically notifies next of kin via WhatsApp

### Step 2: Medical Verification
1. Medical staff reviews death report
2. Clicks "Verify" button in dashboard
3. Adds medical findings and organ viability notes
4. Confirms verification
5. Status changes from "Reported" to "Verified"

### Step 3: Organ Harvesting
1. Surgical team reviews verified report
2. Clicks "Harvest" button
3. Selects organs that were successfully harvested
4. System automatically:
   - Updates donor status to unavailable
   - Finds matching recipients
   - Sends WhatsApp notifications to recipients
   - Creates notifications in system

### Step 4: Recipient Notification
- Recipients receive WhatsApp alerts: "Organs ready: [organ] available for transplant"
- Recipients can see notifications in their dashboard
- Admin can view allocation status

## Templates Created

1. **hospital_register.html** - Hospital registration form
2. **hospital_login.html** - Hospital login interface
3. **hospital_dashboard.html** - Main hospital dashboard with analytics
4. **hospital_report_death.html** - Death reporting form
5. **verify_death.html** - Death verification interface
6. **harvest_organs.html** - Organ harvesting confirmation

## Integration Points

### Notifications System
- Uses existing `Notification` model
- Supports 'hospital' user_type in addition to 'donor' and 'recipient'
- All critical actions create notifications

### WhatsApp Integration
- Leverages existing Twilio integration
- Sends automated messages to:
  - Next of kin when death is reported
  - Recipients when organs are harvested
- Uses `send_whatsapp_message()` function

### Donor Status Management
- Donor marked as `available=False` after organ harvest
- Prevents duplicate allocations
- Status visible in admin dashboard

## Security Features

1. **Role-Based Access Control**
   - Hospital staff can only access their own hospital data
   - Check `hospital_id` before allowing operations

2. **Password Security**
   - Passwords hashed with werkzeug security
   - Secure login with session management

3. **Data Validation**
   - Mobile number validation
   - Email validation
   - Registration number uniqueness

4. **Audit Trail**
   - All reports timestamped
   - Verification dates tracked
   - Notes recorded for documentation

## Navigation Updates

### Navbar Changes
- Added Hospital dropdown menu (visible when not logged in)
- Hospital Dashboard link (when logged in)
- Hospital Logout option

### Home Page Updates
- Added "For Hospitals" card explaining hospital features
- Links to hospital registration and login

## How to Use

### For Hospital Staff:

1. **Register Hospital**
   - Go to Home → Hospital → Register
   - Enter hospital details and credentials
   - System creates account immediately

2. **Report Death**
   - Login to hospital dashboard
   - Click "Report Death" button
   - Search donor by mobile number
   - Fill in medical details
   - Submit (next of kin is notified)

3. **Verify Death**
   - View pending reports in dashboard
   - Click "Verify" on the death report
   - Review donor and medical information
   - Add verification notes
   - Confirm verification

4. **Harvest Organs**
   - Click "Harvest" on verified death report
   - Select organs that were successfully harvested
   - System notifies matching recipients
   - Organs marked as available for transplant

### For Recipients:
- Automatically notified when organs matching their need are available
- Can see notifications in their dashboard
- Can contact hospital for immediate procedure

### For Admins:
- View all death reports and organs harvested in analytics
- Monitor hospital operations
- Track donor-recipient matches
- Export data for regulatory compliance

## Technical Implementation

### Session Management
```python
session['hospital_id'] = hospital.id
session['hospital_name'] = hospital.hospital_name
```

### Database Queries
- Filter death reports by hospital: `DeathReport.query.filter_by(hospital_id=hospital_id)`
- Find pending recipients: `RecipientRequest.query.filter(...status='Pending')`
- Check donor availability: `Donor.query.filter_by(available=True)`

### Notification Flow
1. Create database notification: `create_notification(user_type, user_id, message)`
2. Send WhatsApp: `send_whatsapp_message(mobile, message)`
3. Both happen for critical operations (death reporting, organ harvesting)

## Testing Checklist

- [ ] Hospital registration works
- [ ] Hospital login works
- [ ] Can report death of existing donor
- [ ] Next of kin receives WhatsApp notification
- [ ] Can verify death report
- [ ] Can harvest organs
- [ ] Recipients receive WhatsApp notification
- [ ] Donor marked as unavailable after harvest
- [ ] Dashboard shows correct statistics
- [ ] Organ status updates in admin panel

## Future Enhancements

1. **Medical Documents Upload**
   - Attach CT scans, medical reports
   - Document storage and retrieval

2. **Advanced Matching**
   - HLA typing integration
   - Geographic proximity matching
   - Urgency-based prioritization

3. **Compliance Reporting**
   - Regulatory reports generation
   - Audit logs for compliance
   - Data export for health authorities

4. **Multi-Hospital Networks**
   - Inter-hospital organ transfers
   - Network-wide matching
   - Shared recipient waiting lists

5. **Mobile App**
   - Hospital staff mobile app
   - Real-time notifications
   - Offline functionality

## Support & Troubleshooting

**Q: Hospital registration fails**
- A: Check if mobile/email/registration number already exists

**Q: Death report not submitted**
- A: Ensure donor is found by mobile number and is marked available

**Q: Recipients not receiving notifications**
- A: Check Twilio credentials, ensure phone number format is correct

**Q: Organs not showing as harvested**
- A: Verify death report must be in "Verified" status before harvesting

## API Response Examples

### Hospital Login Success
```json
{
  "status": "success",
  "message": "Welcome, Apollo Hospital!",
  "hospital_id": 1
}
```

### Death Report Submitted
```json
{
  "status": "success",
  "message": "Death report submitted for John Doe. Next of kin notified.",
  "report_id": 15
}
```

### Organs Harvested
```json
{
  "status": "success",
  "message": "Organs harvested: Heart, Liver. Recipients notified via WhatsApp.",
  "organs": ["Heart", "Liver"]
}
```

## System Architecture

```
Hospital Integration Module
├── Models
│   ├── Hospital
│   └── DeathReport
├── Routes
│   ├── Registration & Login
│   ├── Death Reporting
│   ├── Verification
│   └── Harvesting
├── Templates
│   ├── hospital_dashboard
│   ├── hospital_report_death
│   ├── verify_death
│   └── harvest_organs
└── Integration
    ├── WhatsApp (Twilio)
    ├── Notifications (Database)
    └── Donor-Recipient Matching
```

---
**Version:** 1.0  
**Last Updated:** December 5, 2025  
**Status:** Production Ready
