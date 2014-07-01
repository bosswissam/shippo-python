import shippo

shippo.auth = ('wissam+test@mit.edu', 'wissamtest')

print "Creating address..."

resp = shippo.Address.create(
    object_purpose='QUOTE',
    name='Laura Behrens Wu',
    street1='Clayton St.',
    company='Shippo',
    street_no=215,
    phone='+1 555 341 9393',
    city='San Francisco',
    state='CA',
    zipcode='94117',
    country='US',
    email='laura@goshippo.com',
    metadata= 'Customer ID 123456'
)

print 'Success: %r' % (resp, )
