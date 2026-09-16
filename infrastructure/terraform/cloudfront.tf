resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${local.name}-s3"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}
resource "aws_cloudfront_function" "spa" {
  name    = "${local.name}-spa"
  runtime = "cloudfront-js-2.0"
  publish = true
  code    = <<-JS
    function handler(event) {
      var request = event.request;
      if (request.uri.indexOf('.') === -1 || request.uri.indexOf('/members/') === 0) request.uri = '/index.html';
      return request;
    }
  JS
}
resource "aws_cloudfront_response_headers_policy" "security" {
  name = "${local.name}-security"
  security_headers_config {
    content_type_options { override = true }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "no-referrer"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      override                   = true
    }
    content_security_policy {
      content_security_policy = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' https://${aws_s3_bucket.documents.bucket_regional_domain_name} https://${aws_s3_bucket.documents.bucket_domain_name} https://*.execute-api.${var.aws_region}.amazonaws.com https://cognito-idp.${var.aws_region}.amazonaws.com${var.enable_google_login ? " https://${local.oauth_domain}" : ""}; img-src 'self' data: https://${aws_s3_bucket.documents.bucket_regional_domain_name} https://${aws_s3_bucket.documents.bucket_domain_name}; frame-src 'self' https://${aws_s3_bucket.documents.bucket_regional_domain_name} https://${aws_s3_bucket.documents.bucket_domain_name}; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
      override                = true
    }
  }
}
resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  aliases             = var.frontend_domain == "" ? [] : [var.frontend_domain]
  origin {
    origin_id                = "frontend"
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }
  default_cache_behavior {
    target_origin_id       = "frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    min_ttl                = 0
    default_ttl            = 300
    max_ttl                = 31536000
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.spa.arn
    }
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  viewer_certificate {
    cloudfront_default_certificate = var.frontend_domain == ""
    acm_certificate_arn            = var.frontend_domain == "" ? null : var.frontend_certificate_arn
    ssl_support_method             = var.frontend_domain == "" ? null : "sni-only"
    minimum_protocol_version       = var.frontend_domain == "" ? "TLSv1" : "TLSv1.2_2021"
  }
  lifecycle {
    precondition {
      condition     = var.frontend_domain == "" || can(regex(":acm:us-east-1:", var.frontend_certificate_arn))
      error_message = "A custom frontend domain requires an existing ACM certificate in us-east-1."
    }
  }
}
