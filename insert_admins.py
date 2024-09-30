from sqlalchemy import create_engine, text
from werkzeug.security import generate_password_hash

# Database connection details
db_url = 'postgresql://postgres:Phoenix%401011@localhost/fifa_db'  

# Admin data (name, email, plain password)
admins = [
    ('Apple Tan', 'apple@google.com', 'Admin123!'),
    ('Banana Goh', 'banana@google.com', 'Admin123!'),
    ('Cherry Lee', 'cherry@google.com', 'Admin123!'),
    ('Date Mok', 'date@google.com', 'Admin123!'),
    ('Elderberry Goh', 'elderberry@google.com', 'Admin123!'),
    ('Fig Loh', 'fig@google.com', 'Admin123!'),
    ('Grapefruit Lee', 'grapefruit@google.com', 'Admin123!'),
    ('Honeydew Lok', 'honeydew@google.com', 'Admin123!'),
    ('Indian Fig Poh', 'indianfig@google.com', 'Admin123!'),
    ('Jackfruit Yee', 'jackfruit@google.com', 'Admin123!'),
    ('Kiwi Lim', 'kiwi@google.com', 'Admin123!'),
    ('Lime Ang', 'lime@google.com', 'Admin123!'),
    ('Mango Tan', 'mango@google.com', 'Admin123!'),
    ('Nectarine Wei', 'nectarine@google.com', 'Admin123!'),
    ('Orange Joo', 'orange@google.com', 'Admin123!'),
    ('Papaya Teh', 'papaya@google.com', 'Admin123!'),
    ('Quince Koo', 'quince@google.com', 'Admin123!'),
    ('Raspberry Goo', 'raspberry@google.com', 'Admin123!'),
    ('Strawberry Kim', 'strawberry@google.com', 'Admin123!'),
    ('Tangerine Lin', 'tangerine@google.com', 'Admin123!'),
    ('Ugli Fruit Soh', 'uglifruit@google.com', 'Admin123!'),
    ('Vanilla Bean See', 'vanillabean@google.com', 'Admin123!'),
    ('Watermelon Moon', 'watermelon@google.com', 'Admin123!'),
    ('Xigua Ca', 'xigua@google.com', 'Admin123!'),
    ('Yellow Watermelon Ong', 'yellowwatermelon@google.com', 'Admin123!'),
    ('Zucchini Ang', 'zucchini@google.com', 'Admin123!')
]

# Corresponding profile data (bio, phone, address)
admin_profiles = [
    ('Loves tropical fruits and data security.', '91234501', '123 Orchard Lane'),
    ('Enjoys organic farming and sustainable practices.', '91234502', '124 Orchard Lane'),
    ('Passionate about cherries and software engineering.', '91234503', '125 Orchard Lane'),
    ('Expert in dry fruits and database management.', '91234504', '126 Orchard Lane'),
    ('Interested in rare fruits and cryptography.', '91234505', '127 Orchard Lane'),
    ('Adventures in fig recipes and system security.', '91234506', '128 Orchard Lane'),
    ('Grapefruit enthusiast with a knack for coding.', '91234507', '129 Orchard Lane'),
    ('Researcher in melon varieties and user authentication.', '91234508', '130 Orchard Lane'),
    ('Lover of exotic fruits and complex databases.', '91234509', '131 Orchard Lane'),
    ('Jackfruit aficionado and tech innovator.', '91234510', '132 Orchard Lane'),
    ('Kiwi collector and encryption specialist.', '91234511', '133 Orchard Lane'),
    ('Citrus fruit expert and network security analyst.', '91234512', '134 Orchard Lane'),
    ('Tropical fruit enthusiast and data protector.', '91234513', '135 Orchard Lane'),
    ('Nectarine gourmet and privacy advocate.', '91234514', '136 Orchard Lane'),
    ('Oranges lover and cyber security expert.', '91234515', '137 Orchard Lane'),
    ('Papaya planter and information security guru.', '91234516', '138 Orchard Lane'),
    ('Quince connoisseur and digital security advisor.', '91234517', '139 Orchard Lane'),
    ('Raspberry farmer and software developer.', '91234518', '140 Orchard Lane'),
    ('Strawberry specialist and IT security consultant.', '91234519', '141 Orchard Lane'),
    ('Tangerine taster and systems programmer.', '91234520', '142 Orchard Lane'),
    ('Ugli fruit researcher and tech enthusiast.', '91234521', '143 Orchard Lane'),
    ('Vanilla Bean lover and data scientist.', '91234522', '144 Orchard Lane'),
    ('Watermelon whisperer and encryption expert.', '91234523', '145 Orchard Lane'),
    ('Xigua expert and full stack developer.', '91234524', '146 Orchard Lane'),
    ('Specialist in yellow watermelons and machine learning.', '91234525', '147 Orchard Lane'),
    ('Zucchini gourmet and application security analyst.', '91234526', '148 Orchard Lane')
]

# Create database engine
engine = create_engine(db_url)

# SQL query for inserting Admin records
insert_admin_sql = text("""
    INSERT INTO Admin (admin_name, email, password)
    VALUES (:admin_name, :email, :password) RETURNING admin_id
""")

# SQL query for inserting AdminProfile records
insert_profile_sql = text("""
    INSERT INTO AdminProfile (admin_id, bio, phone, address)
    VALUES (:admin_id, :bio, :phone, :address)
""")

# Function to insert admins and their profiles
def insert_admins_with_profiles():
    with engine.connect() as conn:
        for i, admin in enumerate(admins):
            admin_name, email, plain_password = admin
            bio, phone, address = admin_profiles[i]
            hashed_password = generate_password_hash(plain_password)  # Hash the password
            
            # Insert the admin record and get the generated admin_id
            result = conn.execute(insert_admin_sql, {
                'admin_name': admin_name, 
                'email': email, 
                'password': hashed_password
            })
            admin_id = result.fetchone()[0]  # Get the inserted admin's ID
            
            # Insert the corresponding admin profile
            conn.execute(insert_profile_sql, {
                'admin_id': admin_id, 
                'bio': bio, 
                'phone': phone, 
                'address': address
            })

        conn.commit()  # Commit the transaction
        print("All admin users and profiles inserted successfully.")

if __name__ == '__main__':
    insert_admins_with_profiles()  # Insert admins and their profiles
