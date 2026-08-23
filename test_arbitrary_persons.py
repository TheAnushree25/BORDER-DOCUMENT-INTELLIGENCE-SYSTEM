from backend.utils import document_extractor

def test_arbitrary_persons():
    print("========================================")
    print("TESTING EXTRACTION FOR ARBITRARY PERSONS")
    print("========================================")

    # Person 1: Different PAN Card
    pan_text = """INCOME TAX DEPARTMENT
GOVT. OF INDIA
Permanent Account Number Card
XYZKL9876Q
/Name
RAJESH SHARMA
f/Father'sName
SURESH SHARMA
Date of Birth
15/08/1995
Signature"""

    doc_type, ext_pan = document_extractor.extract_document_data(pan_text)
    print("Person 1 (PAN):", ext_pan)
    assert doc_type == "PAN Card"
    assert ext_pan["Full Name"] == "RAJESH SHARMA"
    assert ext_pan["Father's Name"] == "SURESH SHARMA"
    assert ext_pan["PAN Number"] == "XYZKL9876Q"
    assert ext_pan["Date of Birth"] == "15/08/1995"
    print("[OK] Person 1 PAN extracted perfectly!")

    # Person 2: Different Aadhaar Card
    aadhaar_text = """Government of India
Unique Identification Authority of India
Name: PRIYA PATEL
DOB: 22/11/1998
Gender: FEMALE
9876 5432 1098"""

    doc_type, ext_aadhaar = document_extractor.extract_document_data(aadhaar_text)
    print("Person 2 (Aadhaar):", ext_aadhaar)
    assert doc_type == "Aadhaar Card"
    assert ext_aadhaar["Full Name"] == "PRIYA PATEL"
    assert ext_aadhaar["Aadhaar Number"] == "XXXX XXXX 1098"
    assert ext_aadhaar["Date of Birth"] == "22/11/1998"
    assert ext_aadhaar["Gender"] == "FEMALE"
    print("[OK] Person 2 Aadhaar extracted perfectly!")

    # Person 3: Different Passport
    passport_text = """PASSPORT
REPUBLIC OF INDIA
P<INDSINGH<<VIKRAM<<<<<<<<<<<<<<<<<<<<<<<<<<<
Z9876543<5IND9006051M3001011<<<<<<<<<<<<<<04"""

    from backend.utils import mrz
    mrz_res = mrz.parse_td3("P<INDSINGH<<VIKRAM<<<<<<<<<<<<<<<<<<<<<<<<<<<", "Z9876543<5IND9006051M3001011<<<<<<<<<<<<<<04")
    doc_type, ext_pass = document_extractor.extract_document_data(passport_text, mrz_result=mrz_res)
    print("Person 3 (Passport):", ext_pass)
    assert doc_type == "Passport"
    assert ext_pass["Full Name"] == "VIKRAM SINGH"
    assert ext_pass["Passport No."] == "Z9876543"
    print("[OK] Person 3 Passport extracted perfectly!")

    print("\n========================================")
    print("ALL ARBITRARY PERSON TESTS PASSED 100%!")
    print("========================================")

if __name__ == "__main__":
    test_arbitrary_persons()
