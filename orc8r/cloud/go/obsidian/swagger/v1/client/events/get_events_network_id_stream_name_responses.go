// Code generated by go-swagger; DO NOT EDIT.

package events

// This file was generated by the swagger tool.
// Editing this file might prove futile when you re-run the swagger generate command

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"

	"github.com/go-openapi/errors"
	"github.com/go-openapi/runtime"
	"github.com/go-openapi/swag"
	"github.com/go-openapi/validate"

	strfmt "github.com/go-openapi/strfmt"

	models "magma/orc8r/cloud/go/obsidian/swagger/v1/models"
)

// GetEventsNetworkIDStreamNameReader is a Reader for the GetEventsNetworkIDStreamName structure.
type GetEventsNetworkIDStreamNameReader struct {
	formats strfmt.Registry
}

// ReadResponse reads a server response into the received o.
func (o *GetEventsNetworkIDStreamNameReader) ReadResponse(response runtime.ClientResponse, consumer runtime.Consumer) (interface{}, error) {
	switch response.Code() {
	case 200:
		result := NewGetEventsNetworkIDStreamNameOK()
		if err := result.readResponse(response, consumer, o.formats); err != nil {
			return nil, err
		}
		return result, nil
	default:
		result := NewGetEventsNetworkIDStreamNameDefault(response.Code())
		if err := result.readResponse(response, consumer, o.formats); err != nil {
			return nil, err
		}
		if response.Code()/100 == 2 {
			return result, nil
		}
		return nil, result
	}
}

// NewGetEventsNetworkIDStreamNameOK creates a GetEventsNetworkIDStreamNameOK with default headers values
func NewGetEventsNetworkIDStreamNameOK() *GetEventsNetworkIDStreamNameOK {
	return &GetEventsNetworkIDStreamNameOK{}
}

/*GetEventsNetworkIDStreamNameOK handles this case with default header values.

Success
*/
type GetEventsNetworkIDStreamNameOK struct {
	Payload *GetEventsNetworkIDStreamNameOKBodyTuple0
}

func (o *GetEventsNetworkIDStreamNameOK) Error() string {
	return fmt.Sprintf("[GET /events/{network_id}/{stream_name}][%d] getEventsNetworkIdStreamNameOK  %+v", 200, o.Payload)
}

func (o *GetEventsNetworkIDStreamNameOK) GetPayload() *GetEventsNetworkIDStreamNameOKBodyTuple0 {
	return o.Payload
}

func (o *GetEventsNetworkIDStreamNameOK) readResponse(response runtime.ClientResponse, consumer runtime.Consumer, formats strfmt.Registry) error {

	o.Payload = new(GetEventsNetworkIDStreamNameOKBodyTuple0)

	// response payload
	if err := consumer.Consume(response.Body(), o.Payload); err != nil && err != io.EOF {
		return err
	}

	return nil
}

// NewGetEventsNetworkIDStreamNameDefault creates a GetEventsNetworkIDStreamNameDefault with default headers values
func NewGetEventsNetworkIDStreamNameDefault(code int) *GetEventsNetworkIDStreamNameDefault {
	return &GetEventsNetworkIDStreamNameDefault{
		_statusCode: code,
	}
}

/*GetEventsNetworkIDStreamNameDefault handles this case with default header values.

Unexpected Error
*/
type GetEventsNetworkIDStreamNameDefault struct {
	_statusCode int

	Payload *models.Error
}

// Code gets the status code for the get events network ID stream name default response
func (o *GetEventsNetworkIDStreamNameDefault) Code() int {
	return o._statusCode
}

func (o *GetEventsNetworkIDStreamNameDefault) Error() string {
	return fmt.Sprintf("[GET /events/{network_id}/{stream_name}][%d] GetEventsNetworkIDStreamName default  %+v", o._statusCode, o.Payload)
}

func (o *GetEventsNetworkIDStreamNameDefault) GetPayload() *models.Error {
	return o.Payload
}

func (o *GetEventsNetworkIDStreamNameDefault) readResponse(response runtime.ClientResponse, consumer runtime.Consumer, formats strfmt.Registry) error {

	o.Payload = new(models.Error)

	// response payload
	if err := consumer.Consume(response.Body(), o.Payload); err != nil && err != io.EOF {
		return err
	}

	return nil
}

/*GetEventsNetworkIDStreamNameOKBodyTuple0 GetEventsNetworkIDStreamNameOKBodyTuple0 a representation of an anonymous Tuple type
swagger:model GetEventsNetworkIDStreamNameOKBodyTuple0
*/
type GetEventsNetworkIDStreamNameOKBodyTuple0 struct {

	// p0
	// Required: true
	P0 *models.Event `json:"-"` // custom serializer

}

// UnmarshalJSON unmarshals this tuple type from a JSON array
func (o *GetEventsNetworkIDStreamNameOKBodyTuple0) UnmarshalJSON(raw []byte) error {
	// stage 1, get the array but just the array
	var stage1 []json.RawMessage
	buf := bytes.NewBuffer(raw)
	dec := json.NewDecoder(buf)
	dec.UseNumber()

	if err := dec.Decode(&stage1); err != nil {
		return err
	}

	// stage 2: hydrates struct members with tuple elements

	if len(stage1) > 0 {
		var dataP0 models.Event
		buf = bytes.NewBuffer(stage1[0])
		dec := json.NewDecoder(buf)
		dec.UseNumber()
		if err := dec.Decode(&dataP0); err != nil {
			return err
		}
		o.P0 = &dataP0

	}

	return nil
}

// MarshalJSON marshals this tuple type into a JSON array
func (o GetEventsNetworkIDStreamNameOKBodyTuple0) MarshalJSON() ([]byte, error) {
	data := []interface{}{
		o.P0,
	}

	return json.Marshal(data)
}

// Validate validates this get events network ID stream name o k body tuple0
func (o *GetEventsNetworkIDStreamNameOKBodyTuple0) Validate(formats strfmt.Registry) error {
	var res []error

	if err := o.validateP0(formats); err != nil {
		res = append(res, err)
	}

	if len(res) > 0 {
		return errors.CompositeValidationError(res...)
	}
	return nil
}

func (o *GetEventsNetworkIDStreamNameOKBodyTuple0) validateP0(formats strfmt.Registry) error {

	if err := validate.Required("P0", "body", o.P0); err != nil {
		return err
	}

	if o.P0 != nil {
		if err := o.P0.Validate(formats); err != nil {
			if ve, ok := err.(*errors.Validation); ok {
				return ve.ValidateName("P0")
			}
			return err
		}
	}

	return nil
}

// MarshalBinary interface implementation
func (o *GetEventsNetworkIDStreamNameOKBodyTuple0) MarshalBinary() ([]byte, error) {
	if o == nil {
		return nil, nil
	}
	return swag.WriteJSON(o)
}

// UnmarshalBinary interface implementation
func (o *GetEventsNetworkIDStreamNameOKBodyTuple0) UnmarshalBinary(b []byte) error {
	var res GetEventsNetworkIDStreamNameOKBodyTuple0
	if err := swag.ReadJSON(b, &res); err != nil {
		return err
	}
	*o = res
	return nil
}