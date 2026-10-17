// Exercises the actual Android window, Vulkan device, shaderc, swapchain and GPU submission.
#include <SDL3/SDL.h>
#include "nvn/vulkan/vk.h"
#include "nvn/maxwell/glsl_u64.h"
#include <stdlib.h>
#include <string.h>
extern bool vk_frame_begin(const float clear[4]);
extern void vk_frame_end(const char *shot_path);
extern void renderer_flush(void);

static void arithmetic_probe(void) {
    const char source[] = "#version 450\n" GLSL_U64_HELPERS
        "layout(local_size_x=64) in;\n"
        "layout(std430,set=0,binding=0) buffer Data { uvec4 v[1024]; uvec2 sum[1024]; uvec2 diff[1024]; uvec2 shifts[1024]; };\n"
        "void main() { uint i=gl_GlobalInvocationID.x; uvec4 x=v[i]; sum[i]=add64(x.xy,x.zw); diff[i]=sub64(x.xy,x.zw); shifts[i]=uvec2(shf_r(x.y,x.x,i),shf_l(x.y,x.x,i)); }\n";
    VkShaderModule shader = vk_compile_glsl(source, 5, "android-u64-arithmetic");
    if (!shader) FATAL("Android arithmetic probe: shader compilation failed\n");
    VkBufferCreateInfo bi = {.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=1024*40,.usage=VK_BUFFER_USAGE_STORAGE_BUFFER_BIT};
    VmaAllocationCreateInfo ai = {.usage=VMA_MEMORY_USAGE_AUTO_PREFER_HOST,
        .flags=VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT|VMA_ALLOCATION_CREATE_MAPPED_BIT,
        .requiredFlags=VK_MEMORY_PROPERTY_HOST_COHERENT_BIT};
    VkBuffer buffer; VmaAllocation allocation; VmaAllocationInfo info;
    VK_CHECK(vmaCreateBuffer(g_vk.vma,&bi,&ai,&buffer,&allocation,&info));
    uint32_t *words=info.pMappedData;
    uint64_t values[2048], rng=0xa41c750be39d823full;
    const uint64_t edge[]={0,1,0xffffffffull,0x100000000ull,~0ull,0x7100000000ull,0x71cfffffffull,0x7200000000ull};
    for(int i=0;i<2048;i++) {
        rng^=rng<<13; rng^=rng>>7; rng^=rng<<17;
        values[i]=i<64 ? edge[(i/8+i%8)%8] : rng;
        words[i*2]=(uint32_t)values[i]; words[i*2+1]=(uint32_t)(values[i]>>32);
    }
    VkDescriptorSetLayoutBinding binding={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=1,.pBindings=&binding};
    VkDescriptorSetLayout set_layout; VK_CHECK(vkCreateDescriptorSetLayout(g_vk.dev,&li,NULL,&set_layout));
    VkPipelineLayoutCreateInfo pi={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&set_layout};
    VkPipelineLayout layout; VK_CHECK(vkCreatePipelineLayout(g_vk.dev,&pi,NULL,&layout));
    VkComputePipelineCreateInfo ci={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.layout=layout,
        .stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=shader,.pName="main"}};
    VkPipeline pipeline; VK_CHECK(vkCreateComputePipelines(g_vk.dev,VK_NULL_HANDLE,1,&ci,NULL,&pipeline));
    VkDescriptorPoolSize ps={VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1};
    VkDescriptorPoolCreateInfo pc={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=1,.poolSizeCount=1,.pPoolSizes=&ps};
    VkDescriptorPool pool; VK_CHECK(vkCreateDescriptorPool(g_vk.dev,&pc,NULL,&pool));
    VkDescriptorSetAllocateInfo sa={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&set_layout};
    VkDescriptorSet set; VK_CHECK(vkAllocateDescriptorSets(g_vk.dev,&sa,&set));
    VkDescriptorBufferInfo db={buffer,0,bi.size};
    VkWriteDescriptorSet write={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=set,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&db};
    vkUpdateDescriptorSets(g_vk.dev,1,&write,0,NULL);
    VkCommandBuffer cb=vk_cmd();
    vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);
    vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,0,NULL);
    vkCmdDispatch(cb,16,1,1);
    VkMemoryBarrier2 barrier={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER_2,.srcStageMask=VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT,
        .srcAccessMask=VK_ACCESS_2_SHADER_WRITE_BIT,.dstStageMask=VK_PIPELINE_STAGE_2_HOST_BIT,.dstAccessMask=VK_ACCESS_2_HOST_READ_BIT};
    VkDependencyInfo dependency={.sType=VK_STRUCTURE_TYPE_DEPENDENCY_INFO,.memoryBarrierCount=1,.pMemoryBarriers=&barrier};
    vkCmdPipelineBarrier2(cb,&dependency);
    renderer_flush();
    for(int i=0;i<1024;i++) {
        uint64_t a=values[i*2], b=values[i*2+1], sum=a+b, diff=a-b;
        unsigned shift=(unsigned)i&31;
        uint32_t expected[]={sum,sum>>32,diff,diff>>32,(uint32_t)(a>>shift),(uint32_t)((a<<shift)>>32)};
        const unsigned offsets[]={4096+i*2,4097+i*2,6144+i*2,6145+i*2,8192+i*2,8193+i*2};
        for(int j=0;j<6;j++) if(words[offsets[j]]!=expected[j])
            FATAL("Android arithmetic mismatch at case %d op %d: %x != %x\n",i,j,words[offsets[j]],expected[j]);
    }
    LOG("[android-probe] SUCCESS: 6144 GPU arithmetic results match CPU uint64 reference\n");
    vkDestroyDescriptorPool(g_vk.dev,pool,NULL); vkDestroyPipeline(g_vk.dev,pipeline,NULL);
    vkDestroyPipelineLayout(g_vk.dev,layout,NULL); vkDestroyDescriptorSetLayout(g_vk.dev,set_layout,NULL);
    vkDestroyShaderModule(g_vk.dev,shader,NULL); vmaDestroyBuffer(g_vk.vma,buffer,allocation);
}

int android_graphics_probe(void) {
    extern void ui_window_init(void);
    ui_window_init();
    { extern void android_set_status(const char *message); android_set_status(""); }
    arithmetic_probe();
    LOG("[android-probe] GPU %s, Vulkan %u.%u.%u, host-import=%d\n", g_vk.props.deviceName,
        VK_API_VERSION_MAJOR(g_vk.props.apiVersion), VK_API_VERSION_MINOR(g_vk.props.apiVersion),
        VK_API_VERSION_PATCH(g_vk.props.apiVersion), g_vk.host_import);
    int shown = 0;
    for (int i = 0; i < 180; i++) {
        SDL_Event event;
        while (SDL_PollEvent(&event)) if (event.type == SDL_EVENT_QUIT) return 1;
        const float color[4] = {0.025f, 0.12f + (float)i / 1000, 0.2f, 1};
        if (vk_frame_begin(color)) { vk_frame_end(NULL); shown++; }
        SDL_Delay(16);
    }
    VK_CHECK(vkDeviceWaitIdle(g_vk.dev));
    LOG("[android-probe] SUCCESS: %d frames presented on real hardware\n", shown);
    return shown ? 0 : 1;
}
