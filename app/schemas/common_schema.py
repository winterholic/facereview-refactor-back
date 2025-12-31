from marshmallow import Schema, fields

class SuccessResponseSchema(Schema):
    result = fields.String(dump_default="success", metadata={'description': '성공 여부'})
    message = fields.String(metadata={'description': '안내 메시지'})