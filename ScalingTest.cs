using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Azure.Functions.Worker;
using Microsoft.Extensions.Logging;

namespace KedaScalingTest;

public class ScalingTest
{
    private readonly ILogger<ScalingTest> _logger;

    public ScalingTest(ILogger<ScalingTest> logger)
    {
        _logger = logger;
    }

    [Function("ScalingTest")]
    public IActionResult Run([HttpTrigger(AuthorizationLevel.Anonymous, "get", "post")] HttpRequest req)
    {
        _logger.LogInformation("C# HTTP trigger function processed a request.");
        return new OkObjectResult("Welcome to Azure Functions!");
    }
}